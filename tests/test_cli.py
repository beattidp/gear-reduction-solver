"""Unit tests for the CLI interface."""

import json
from io import StringIO
import pytest
from unittest.mock import patch

from gear_reduction.cli import main, parse_teeth_arg


def test_parse_teeth_arg() -> None:
    assert parse_teeth_arg("11-15") == [11, 12, 13, 14, 15]
    assert parse_teeth_arg("12,16,20") == [12, 16, 20]
    assert parse_teeth_arg("11-13,20,25-27") == [11, 12, 13, 20, 25, 26, 27]


def test_cli_exact_solution(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["-r", "2:1", "-n", "2"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Gear Reduction Solutions" in captured
    assert "2/1" in captured


def test_cli_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["-r", "4:1", "-n", "2", "--json"])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["target_ratio"] == "4/1"
    assert data["solutions_count"] == 2
    assert len(data["solutions"]) == 2
    assert data["solutions"][0]["relative_cost"] == 1.0


def test_cli_unattainable_without_approx(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["-r", "71:1"])
    assert code == 1
    captured = capsys.readouterr().out
    assert "No gear reduction solutions found" in captured


def test_cli_unattainable_with_approx(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["-r", "71:1", "--approx", "-n", "1"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Dev %" in captured
    assert "%" in captured
