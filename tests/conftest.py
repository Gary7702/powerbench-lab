"""Entirely synthetic shared test data; no employer reports or personal material."""

import pytest

from powerbench.models import Conditions


@pytest.fixture
def conditions() -> Conditions:
    return Conditions("TEST", "1", 10.0, 5.0, 500.0, "1")


@pytest.fixture
def table() -> list[list[object]]:
    return [
        ["No.", "Io", "Vo", "Vi", "Ii", "Po", "Pi", "Ploss", "Effi"],
        [1, 0, 5, 10, 0, 0, 0, 0, 0],
        [2, 1, 5, 10, 0.625, 5, 6.25, 1.25, 0.8],
        [3, 2, 4.99, 10, 1.2475, 9.98, 12.475, 2.495, 0.8],
    ]
