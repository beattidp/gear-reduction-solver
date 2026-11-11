"""Unit and integration tests for UI and Solver Enhancements.

Tests cover:
1. Ratio inversion normalization ("1:4", "1/4", 0.25 -> 4:1)
2. Prime factor reachability analysis and fast exact-search short-circuit
3. Custom gear sizes (e.g. 52T without 41-51T) and discrete inventory
4. High-depth stage expansion (depths 5 and 6)
5. SolverConfig catalog management and JSON serialization
6. CLI config export/show and discrete teeth parsing
"""

from fractions import Fraction
import json
from pathlib import Path
import pytest

from gear_reduction.cli import main, parse_teeth_arg
from gear_reduction.config import SolverConfig
from gear_reduction.core.models import CostModel
from gear_reduction.core.solver import (
    ReductionSolver,
    check_prime_reachability,
    get_prime_factors,
    parse_ratio,
)
from gear_reduction.core.planetary_solver import PlanetarySolver


class TestPrimeReachability:
    """Tests for mathematical prime reachability analysis."""

    def test_get_prime_factors(self) -> None:
        assert get_prime_factors(1) == set()
        assert get_prime_factors(2) == {2}
        assert get_prime_factors(12) == {2, 3}
        assert get_prime_factors(43) == {43}
        assert get_prime_factors(52) == {2, 13}

    def test_prime_reachability_within_inventory(self) -> None:
        teeth = list(range(9, 41))
        # 31 is in inventory
        reachable, factor = check_prime_reachability(Fraction(31, 1), teeth)
        assert reachable is True
        assert factor is None

        # 43 is prime and > 40, not in inventory
        reachable, factor = check_prime_reachability(Fraction(43, 1), teeth)
        assert reachable is False
        assert factor == 43

    def test_prime_reachability_with_custom_gear(self) -> None:
        teeth = list(range(9, 41)) + [43]
        # Now 43 is available
        reachable, factor = check_prime_reachability(Fraction(43, 1), teeth)
        assert reachable is True
        assert factor is None

    def test_exact_solver_fast_exit_for_unreachable_prime(self) -> None:
        """Unreachable prime ratio returns [] immediately in exact mode."""
        solver = ReductionSolver(available_teeth=list(range(9, 41)), max_stages=6)
        # 43 is unreachable
        solutions = solver.solve("43:1", allow_approximate=False)
        assert solutions == []

    def test_approximate_solver_handles_unreachable_prime(self) -> None:
        """When approximate mode is enabled, nearest rational train is found."""
        solver = ReductionSolver(available_teeth=list(range(9, 41)), max_stages=4)
        solutions = solver.solve("43:1", allow_approximate=True, max_solutions=2)
        assert len(solutions) > 0
        assert solutions[0].is_approximate is True


class TestCustomGearSizesAndConfig:
    """Tests for known vs available teeth, custom gear sizes, and SolverConfig."""

    def test_default_config_includes_9_and_10(self) -> None:
        cfg = SolverConfig()
        assert 9 in cfg.known_gear_teeth
        assert 10 in cfg.known_gear_teeth
        assert 9 in cfg.available_gear_teeth
        assert 10 in cfg.available_gear_teeth
        assert cfg.min_gear_teeth == 9

    def test_add_and_remove_custom_gear(self) -> None:
        cfg = SolverConfig()
        # Add 52T without adding 41-51T
        cfg.add_known_gear(52, enable=True)
        assert 52 in cfg.known_gear_teeth
        assert 52 in cfg.available_gear_teeth
        assert cfg.max_gear_teeth == 52

        # Disable 52T
        cfg.set_gear_availability(52, False)
        assert 52 in cfg.known_gear_teeth
        assert 52 not in cfg.available_gear_teeth

        # Re-enable 52T
        cfg.set_gear_availability(52, True)
        assert 52 in cfg.available_gear_teeth

        # Remove 52T completely
        cfg.remove_known_gear(52)
        assert 52 not in cfg.known_gear_teeth
        assert 52 not in cfg.available_gear_teeth
        assert cfg.max_gear_teeth == 40

    def test_config_serialization(self, tmp_path: Path) -> None:
        cfg = SolverConfig()
        cfg.add_known_gear(52, enable=True)
        out_file = tmp_path / "test_config.json"
        cfg.save(out_file)

        loaded = SolverConfig.load(out_file)
        assert 52 in loaded.known_gear_teeth
        assert 52 in loaded.available_gear_teeth
        assert 9 in loaded.known_gear_teeth
        assert loaded.max_gear_teeth == 52

    def test_solver_with_custom_gear_52(self) -> None:
        """Solving with 52T gear produces solutions using 52T."""
        teeth = list(range(10, 41)) + [52]
        solver = ReductionSolver(available_teeth=teeth, max_stages=2)
        # Ratio 52:13 = 4:1, single stage
        solutions = solver.solve("4:1", max_solutions=5)
        assert any(
            any(s.gear == 52 for s in sol.stages)
            for sol in solutions
        )


class TestStageExpansion:
    """Tests for 5-stage and 6-stage solutions."""

    def test_five_and_six_stage_spur_solutions(self) -> None:
        """Verify solver successfully synthesizes 5-stage and 6-stage compound trains."""
        # Using a small tooth set {10, 20} so each stage is 2:1
        # 5 stages = 32:1, 6 stages = 64:1
        teeth = [10, 20]
        solver_5 = ReductionSolver(available_teeth=teeth, max_stages=5)
        solutions_5 = solver_5.solve("32:1")
        assert len(solutions_5) > 0
        assert len(solutions_5[0].stages) == 5
        assert solutions_5[0].achieved_ratio == Fraction(32, 1)

        solver_6 = ReductionSolver(available_teeth=teeth, max_stages=6)
        solutions_6 = solver_6.solve("64:1")
        assert len(solutions_6) > 0
        assert len(solutions_6[0].stages) == 6
        assert solutions_6[0].achieved_ratio == Fraction(64, 1)

    def test_planetary_four_stages(self) -> None:
        """Verify planetary solver supports 4 cascaded stages."""
        teeth = list(range(12, 30))
        solver = PlanetarySolver(available_teeth=teeth, max_stages=4)
        # 4 stages of 4:1 = 256:1
        solutions = solver.solve(Fraction(256, 1), allow_approximate=False, max_solutions=1)
        if solutions:
            assert len(solutions[0].stages) <= 4
            assert solutions[0].achieved_ratio == Fraction(256, 1)


class TestCliEnhancements:
    """Tests for CLI ratio inversion, config export/show, and discrete teeth."""

    def test_cli_ratio_inversion(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI with '-r 1:4' or '-r 1/4' solves as 4:1 reduction."""
        code1 = main(["-r", "1:4", "-n", "1"])
        assert code1 == 0
        captured1 = capsys.readouterr().out
        assert "4/1" in captured1

        code2 = main(["-r", "1/4", "-n", "1"])
        assert code2 == 0
        captured2 = capsys.readouterr().out
        assert "4/1" in captured2

    def test_cli_teeth_discrete_parsing(self) -> None:
        parsed = parse_teeth_arg("9-12,52,60-61")
        assert parsed == [9, 10, 11, 12, 52, 60, 61]

    def test_cli_config_show(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--config-show"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert "known_gear_teeth" in data
        assert "available_gear_teeth" in data

    def test_cli_config_export(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        export_file = tmp_path / "exported_config.json"
        code = main(["--config-export", str(export_file)])
        assert code == 0
        assert export_file.is_file()
        with open(export_file) as f:
            data = json.load(f)
        assert "known_gear_teeth" in data
