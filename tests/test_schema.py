"""Tests validating JSON outputs from CLI and Web against the formal JSON Schema using jsonschema."""

import json
from pathlib import Path
import jsonschema
import pytest

from gear_reduction.cli import main


class TestJsonSchemaValidation:
    """Verifies that CLI and Web JSON outputs match schema/gear_reduction_solution.schema.json."""

    @pytest.fixture
    def schema_data(self) -> dict:
        schema_path = Path(__file__).resolve().parent.parent / "schema" / "gear_reduction_solution.schema.json"
        assert schema_path.is_file()
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_schema_file_is_valid_json_schema(self, schema_data: dict) -> None:
        """Verifies schema is a valid Draft 2020-12 schema specification."""
        validator_cls = jsonschema.validators.validator_for(schema_data)
        validator_cls.check_schema(schema_data)

    def test_cli_spur_json_validates_against_schema(self, capsys: pytest.CaptureFixture[str], schema_data: dict) -> None:
        """Verifies CLI spur output strictly validates against the schema."""
        ret = main(["-r", "10:1", "-n", "3", "--json"])
        assert ret == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)

        # Full Draft 2020-12 validation
        jsonschema.validate(instance=data, schema=schema_data)

        # Validate envelope fields
        assert data["mode"] == "spur"
        assert data["solutions_count"] == 3
        assert len(data["solutions"]) == 3

    def test_cli_planetary_json_validates_against_schema(self, capsys: pytest.CaptureFixture[str], schema_data: dict) -> None:
        """Verifies CLI planetary output strictly validates against the schema."""
        ret = main(["-r", "4:1", "--planetary", "-n", "3", "--json"])
        assert ret == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)

        # Full Draft 2020-12 validation
        jsonschema.validate(instance=data, schema=schema_data)
        assert data["mode"] == "planetary"
        assert len(data["solutions"]) > 0
        assert data["solutions"][0]["type"] == "planetary"

    def test_cli_all_mode_json_validates_against_schema(self, capsys: pytest.CaptureFixture[str], schema_data: dict) -> None:
        """Verifies CLI '--type all' output strictly validates against the schema."""
        ret = main(["-r", "4:1", "--type", "all", "-n", "2", "--json"])
        assert ret == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)

        # Full Draft 2020-12 validation
        jsonschema.validate(instance=data, schema=schema_data)
        assert data["mode"] == "all"
        assert "spur_solutions" in data
        assert "planetary_solutions" in data

    def test_web_copied_solutions_array_validates_against_schema(self, capsys: pytest.CaptureFixture[str], schema_data: dict) -> None:
        """Verifies the JSON copied from the Web UI (pure array of solutions) validates against the schema."""
        ret = main(["-r", "10:1", "-n", "2", "--json"])
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        web_copied_spur_array = data["solutions"]

        # Validate pure array of solutions (as downloaded / copied from Web UI)
        jsonschema.validate(instance=web_copied_spur_array, schema=schema_data)

        # Single solution validation
        jsonschema.validate(instance=web_copied_spur_array[0], schema=schema_data)
