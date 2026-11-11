# PowerBench Lab

**面向电源模块测试的 Python 数据处理工程：从仪器导出到可追溯数据、指标和离线报告。**

[English README](README.md) · [算法与限制](docs/methodology.md) · [工程结构](docs/architecture.md)

## 这个项目展示什么

它不是给旧脚本换个名字，而是把测试数据处理拆成可独立验证的环节：

- 识别文件名中的样品、通道、输入/输出电压、频率及模式；
- 读取规定格式的 PDF 表格，保留源页、表、行与输入文件哈希；
- 检查缺列、非有限值、功率/效率一致性，并明确报告错误；
- 计算效率峰值、负载调整率，以及相同实际负载下的线性调整率；
- 导出结构化 CSV/JSON、Excel、SVG/PNG 曲线与离线交互 HTML；
- 用自动化测试、静态检查和 CI 保证改动有据可查。

**仓库所有示例均为人工生成的合成数据，不是实际器件性能。** 不包含工作单位报告、原始表格、简历、联系方式或机密型号。模式编号与设备物理模式的对应关系必须以设备资料为准。

## 快速运行

Python 3.11 及以上，在项目目录中执行：

```bash
python -m venv .venv
# Windows PowerShell：.venv\Scripts\Activate.ps1
# macOS / Linux：source .venv/bin/activate
python -m pip install -e ".[dev]"
powerbench demo --output outputs/demo --legacy-wide
```

打开 `outputs/demo/report.html`，可以筛选工况、切换效率/输出电压/损耗、检查每个点的来源。依赖安装后可离线运行。输出包含 8 条曲线、96 个点及刻意加入的异常效率示例。

每次请使用**新的或空的输出目录**，程序不会覆盖已有报告。

## 处理自己的数据

```bash
powerbench validate ./inputs --json
powerbench analyze ./inputs --output outputs/run-01 --config examples/settings.toml
powerbench analyze ./inputs --output outputs/run-02 --loads 0,1,2 --log-x
powerbench logs examples/synthetic-voltage.txt --output outputs/logs --headers examples/voltage-headers.json
```

`--recursive` 才会包含子目录；`--strict` 会把警告也视作失败。默认批处理保留成功文件，同时把失败写入诊断并返回非零状态。`python -m powerbench` 也可调用同一入口。

## 必须理解的计算口径

1. **效率保留仪器报告原值。** 百分数显示是原比例 × 100；`Pout / Pin` 仅用于一致性检查，不会覆盖原值。
2. **`inf` 不等于 0。** 非有限效率保留为缺失并产生警告；真实的空载零效率保留为零。
3. **负载调整率的分母是测得 Vout 的算术平均值。** 正负偏差和最大最小跨度是描述性指标，不是自动合格判定。
4. **不同 Vin 必须在同一实际负载上比较。** 在共同测量范围内线性插值，绝不外推；默认取交集下限、中点、上限，而不是假设第几行就是额定半载。
5. **原始单位约定明确。** A、V、W、kHz，效率默认为比例；未知单位、扫描 PDF、任意排版及 Excel 反向导入不在当前支持范围。

## 验证

```bash
python -m pytest --cov=powerbench --cov-report=term-missing
ruff check .
ruff format --check .
mypy src/powerbench
python -m build
```

公开测试使用合成表格与 PDF 读取边界测试替身；历史真实报告只用于私有核对，不随仓库发布。

## 作为求职作品如何介绍

可以说：“将电源模块测试的临时数据处理脚本工程化，加入结构化数据模型、明确的数值与异常处理、可配置命令行、可追溯报告和自动测试。”

不要声称它已经用于自动批准量产、覆盖所有仪器格式、获得某个未测量的提速比例，或把本次扩展功能描述为当年已完成的工作。演示时应能够解释为何不把 `inf` 改成零、为何用实际负载插值，以及为何保留原始工况和来源。

作者：Gary Feng。许可：[MIT](LICENSE)。
