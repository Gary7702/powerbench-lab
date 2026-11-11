"""Voltage log parsing, encodings, malformed lines, and positional safety."""

import pytest

from powerbench.logs import parse_log, wide_log_rows
from powerbench.models import ParseError

TEXT = "header\nnow......ch1......读取输出电压......3.3 V\nnow......ch2......读取输出电压......1800 mV\nnow......ch1......other......99\n"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_utf_encodings_metric_and_unit_conversion(tmp_path, encoding):
    path = tmp_path / "synthetic.log"
    path.write_bytes(TEXT.encode(encoding))
    result = parse_log(path)
    assert [v.value for v in result.values] == [3.3, 1.8]
    assert [v.line for v in result.values] == [2, 3]
    assert [v.sequence for v in result.values] == [1, 2]
    assert result.issues[0].code == "short_log_line"


def test_failed_files_excluded_unless_requested(tmp_path):
    path = tmp_path / "sample_Fail.log"
    path.write_text(TEXT, encoding="utf-8")
    assert parse_log(path).skipped
    assert len(parse_log(path, include_failed=True).values) == 2


@pytest.mark.parametrize("value", ["", "inf", "NaN", "1.2 garbage", "1e999", "3.3A"])
def test_invalid_target_values_are_not_zero_or_silently_skipped(tmp_path, value):
    path = tmp_path / "synthetic.log"
    path.write_text(f"now......ch......读取输出电压......{value}\n", encoding="utf-8")
    result = parse_log(path)
    assert result.values == ()
    assert all(issue.severity == "error" for issue in result.issues)


def test_explicit_codec_supports_nonutf_logs(tmp_path):
    path = tmp_path / "synthetic.log"
    path.write_bytes(TEXT.encode("gb18030"))
    with pytest.raises(ParseError, match="encoding"):
        parse_log(path)
    assert len(parse_log(path, encoding="gb18030").values) == 2
    with pytest.raises(ParseError):
        parse_log(path, encoding="not-a-codec")


def test_empty_metric_or_delimiter_rejected(tmp_path):
    with pytest.raises(ParseError):
        parse_log(tmp_path / "unused", delimiter="")
    with pytest.raises(ParseError):
        parse_log(tmp_path / "unused", metric="")


def test_wide_export_requires_exact_explicit_headers(tmp_path):
    path = tmp_path / "synthetic.log"
    path.write_text(TEXT, encoding="utf-8")
    result = parse_log(path)
    assert wide_log_rows((result,), ("ch1_v", "ch2_v")) == [[path.name, 3.3, 1.8]]
    with pytest.raises(ParseError, match="misalignment"):
        wide_log_rows((result,), ("one",))
    for headers in ((), ("",), (" ",), ("same", "same")):
        with pytest.raises(ParseError):
            wide_log_rows((result,), headers)


def test_wide_export_cannot_shift_data_after_rejected_value(tmp_path):
    path = tmp_path / "synthetic.log"
    path.write_text(TEXT + "now......ch......读取输出电压......bad", encoding="utf-8")
    with pytest.raises(ParseError, match="rejected"):
        wide_log_rows((parse_log(path),), ("a", "b"))


def test_skipped_log_does_not_create_empty_wide_row(tmp_path):
    path = tmp_path / "FAIL.log"
    path.write_text(TEXT, encoding="utf-8")
    assert wide_log_rows((parse_log(path),), ("a", "b")) == []
