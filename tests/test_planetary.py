"""Tests for epicyclic (planetary) gear stages, cost models, solver engine, and CLI."""

import json
from fractions import Fraction
import pytest

from gear_reduction.cli import main
from gear_reduction.core.planetary import (
    PlanetaryCostModel,
    PlanetarySolution,
    PlanetaryStage,
    PlanetaryStator,
)
from gear_reduction.core.planetary_solver import PlanetarySolver


class TestPlanetaryStage:
    """Tests for PlanetaryStage mechanical invariants and kinematics."""

    def test_valid_stage_ring_stator(self) -> None:
        """Validates standard ring-stator planetary stage (S=12, P=12, R=36, N=3)."""
        stage = PlanetaryStage(
            sun=12,
            planet=12,
            ring=36,
            stator=PlanetaryStator.RING,
            planets_count=3,
        )
        assert stage.sun == 12
        assert stage.planet == 12
        assert stage.ring == 36
        assert stage.planets_count == 3
        assert stage.stator == PlanetaryStator.RING
        assert stage.input_element == "sun"
        assert stage.output_element == "carrier"
        assert not stage.is_inverted
        # Ratio = (S + R) / S = (12 + 36) / 12 = 4:1
        assert stage.ratio == Fraction(4, 1)

    def test_valid_stage_carrier_stator(self) -> None:
        """Validates carrier-stator (stationary pins) stage inverting rotation."""
        stage = PlanetaryStage(
            sun=12,
            planet=12,
            ring=36,
            stator=PlanetaryStator.CARRIER,
            planets_count=3,
        )
        assert stage.input_element == "sun"
        assert stage.output_element == "ring"
        assert stage.is_inverted
        # Ratio = R / S = 36 / 12 = 3:1
        assert stage.ratio == Fraction(3, 1)

    def test_valid_stage_sun_stator(self) -> None:
        """Validates sun-stator low-ratio stage."""
        stage = PlanetaryStage(
            sun=12,
            planet=12,
            ring=36,
            stator=PlanetaryStator.SUN,
            planets_count=3,
        )
        assert stage.input_element == "ring"
        assert stage.output_element == "carrier"
        assert not stage.is_inverted
        # Ratio = (S + R) / R = (12 + 36) / 36 = 48 / 36 = 4 / 3
        assert stage.ratio == Fraction(4, 3)

    def test_coaxiality_violation_rejected(self) -> None:
        """Ensures stages violating R = S + 2P are rejected."""
        with pytest.raises(ValueError, match="Coaxiality constraint violated"):
            PlanetaryStage(
                sun=12,
                planet=12,
                ring=35,  # Should be 36
                stator=PlanetaryStator.RING,
            )

    def test_assembly_condition_violation_rejected(self) -> None:
        """Ensures stages violating (S + R) % N == 0 are rejected."""
        # S=11, P=11, R=33 -> (11 + 33) = 44, 44 % 3 = 2 != 0
        with pytest.raises(ValueError, match="Assembly condition violated"):
            PlanetaryStage(
                sun=11,
                planet=11,
                ring=33,
                stator=PlanetaryStator.RING,
                planets_count=3,
            )

    def test_clearance_condition_violation_rejected(self) -> None:
        """Ensures stages where adjacent planets collide are rejected."""
        # For N=4 planets: 4 planets at 90 deg.
        # If planets are very large relative to sun, they collide.
        # S=8, P=30, R=68.
        # (S+P)*sin(pi/4) = 38 * 0.7071 = 26.87 <= P+2 = 32.
        with pytest.raises(ValueError, match="Adjacent planet clearance condition violated"):
            PlanetaryStage(
                sun=8,
                planet=30,
                ring=68,
                stator=PlanetaryStator.RING,
                planets_count=4,
            )


class TestPlanetaryCostModel:
    """Tests for PlanetaryCostModel calculation."""

    def test_single_stage_cost(self) -> None:
        """Verifies integer fabrication and assembly cost for S=12, P=12, R=36, N=3."""
        stage = PlanetaryStage(
            sun=12,
            planet=12,
            ring=36,
            stator=PlanetaryStator.RING,
            planets_count=3,
        )
        cost_model = PlanetaryCostModel(
            ring_multiplier=1.5,
            stage_penalty=60,
            teeth_multiplier=1.0,
        )
        # S(12) + 3*P(36) + 1.5*R(54) = 102. Stage penalty = 60. Total = 162.
        assert cost_model.compute_cost([stage]) == 162


class TestPlanetarySolver:
    """Tests for PlanetarySolver search algorithm."""

    def test_solve_exact_single_stage_ring(self) -> None:
        """Finds exact single-stage solution with Ring stator for 4:1 ratio."""
        solver = PlanetarySolver(
            available_teeth=list(range(11, 41)),
            max_stages=2,
            max_ring_teeth=120,
        )
        solutions = solver.solve(
            target_ratio=Fraction(4, 1),
            stator="ring",
            max_solutions=3,
        )
        assert len(solutions) > 0
        best = solutions[0]
        assert best.achieved_ratio == Fraction(4, 1)
        assert len(best.stages) == 1
        assert best.stages[0].stator == PlanetaryStator.RING
        assert best.stages[0].ratio == Fraction(4, 1)

    def test_solve_exact_single_stage_carrier(self) -> None:
        """Finds exact single-stage solution with Carrier stator (inverted) for 3:1 ratio."""
        solver = PlanetarySolver(
            available_teeth=list(range(11, 41)),
            max_stages=2,
            max_ring_teeth=120,
        )
        solutions = solver.solve(
            target_ratio=Fraction(3, 1),
            stator="carrier",
            max_solutions=3,
        )
        assert len(solutions) > 0
        best = solutions[0]
        assert best.achieved_ratio == Fraction(3, 1)
        assert best.stages[0].stator == PlanetaryStator.CARRIER
        assert best.stages[0].is_inverted
        assert best.is_inverted

    def test_solve_exact_single_stage_sun(self) -> None:
        """Finds exact single-stage solution with Sun stator for 4:3 ratio."""
        solver = PlanetarySolver(
            available_teeth=list(range(11, 41)),
            max_stages=2,
            max_ring_teeth=120,
        )
        solutions = solver.solve(
            target_ratio=Fraction(4, 3),
            stator="sun",
            max_solutions=3,
        )
        assert len(solutions) > 0
        best = solutions[0]
        assert best.achieved_ratio == Fraction(4, 3)
        assert best.stages[0].stator == PlanetaryStator.SUN

    def test_solve_multi_stage_planetary(self) -> None:
        """Finds cascaded 2-stage planetary solution for 16:1 ratio (4:1 x 4:1)."""
        solver = PlanetarySolver(
            available_teeth=list(range(11, 41)),
            max_stages=2,
            max_ring_teeth=120,
        )
        solutions = solver.solve(
            target_ratio=Fraction(16, 1),
            stator="ring",
            max_solutions=3,
        )
        assert len(solutions) > 0
        best = solutions[0]
        assert best.achieved_ratio == Fraction(16, 1)
        assert len(best.stages) == 2
        assert best.stages[0].ratio * best.stages[1].ratio == Fraction(16, 1)

    def test_solve_approximate_when_exact_unreachable(self) -> None:
        """Finds approximate planetary solution for prime target ratio."""
        solver = PlanetarySolver(
            available_teeth=list(range(11, 41)),
            max_stages=2,
            max_ring_teeth=60,
        )
        # 273/10 = 27.3 is unreachable exactly within 2 stages of ring<=60
        solutions = solver.solve(
            target_ratio=Fraction(273, 10),
            allow_approximate=True,
            max_solutions=3,
        )
        assert len(solutions) > 0
        assert any(s.is_approximate for s in solutions)
        assert solutions[0].deviation_percentage is not None


class TestPlanetaryCLI:
    """Tests CLI integration for planetary gear options."""

    def test_cli_planetary_exact_solution(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Tests CLI invocation with --planetary flag."""
        ret = main(["-r", "4:1", "--planetary"])
        assert ret == 0
        out, _ = capsys.readouterr()
        assert "Planetary Gear Reduction Solutions for Target Ratio 4:1" in out
        assert "Fixed:" in out

    def test_cli_planetary_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Tests CLI with --planetary and --json."""
        ret = main(["-r", "4:1", "--planetary", "--json"])
        assert ret == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["mode"] == "planetary"
        assert "planetary_solutions" in data
        assert len(data["planetary_solutions"]) > 0
        assert data["planetary_solutions"][0]["type"] == "planetary"

    def test_cli_type_all_runs_both_solvers(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Tests CLI with --type all running both spur and planetary solvers."""
        ret = main(["-r", "4:1", "--type", "all", "--json"])
        assert ret == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert "spur_solutions" in data
        assert "planetary_solutions" in data
