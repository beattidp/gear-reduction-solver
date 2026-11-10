"""Unit tests for exact gear reduction solving."""

from fractions import Fraction
import pytest

from gear_reduction.core.models import CostModel
from gear_reduction.core.solver import ReductionSolver, parse_ratio


class TestRatioParsing:
    """Tests for ratio string and numeric parsing."""

    def test_parse_colon_ratio(self) -> None:
        assert parse_ratio("10:1") == Fraction(10, 1)
        assert parse_ratio("25:2") == Fraction(25, 2)
        assert parse_ratio(" 7.5 : 1 ") == Fraction(15, 2)

    def test_parse_slash_ratio(self) -> None:
        assert parse_ratio("10/1") == Fraction(10, 1)
        assert parse_ratio("25/2") == Fraction(25, 2)

    def test_parse_numeric_ratio(self) -> None:
        assert parse_ratio(10) == Fraction(10, 1)
        assert parse_ratio(12.5) == Fraction(25, 2)
        assert parse_ratio("10") == Fraction(10, 1)

    def test_invalid_ratio_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ratio("-5:1")
        with pytest.raises(ValueError):
            parse_ratio("0:1")
        with pytest.raises(ValueError):
            parse_ratio("invalid")


class TestExactSolver:
    """Tests for exact solution generation, sorting, and cost weights."""

    @pytest.fixture
    def standard_solver(self) -> ReductionSolver:
        """Returns solver with standard 11T-40T gears."""
        return ReductionSolver(available_teeth=list(range(11, 41)))

    def test_exact_single_stage_ratio(self, standard_solver: ReductionSolver) -> None:
        """Ratio 2:1 is achievable with single stage (e.g. 11:22, 12:24, 13:26, etc.)."""
        solutions = standard_solver.solve(target_ratio="2:1", max_solutions=3)
        assert len(solutions) == 3
        for sol in solutions:
            assert sol.achieved_ratio == Fraction(2, 1)
            assert sol.is_approximate is False
            assert sol.deviation_percentage is None

        # The lowest cost solution must have relative_cost == 1.0
        assert solutions[0].relative_cost == 1.0
        # Check ascending order of relative cost
        for i in range(len(solutions) - 1):
            assert solutions[i].relative_cost <= solutions[i + 1].relative_cost

        # For 2:1 single stage: smallest teeth is 11T -> 22T (sum 33 + 50 = 83)
        cheapest = solutions[0]
        assert len(cheapest.stages) == 1
        assert cheapest.stages[0].pinion == 11
        assert cheapest.stages[0].gear == 22
        assert cheapest.cost == 83

    def test_exact_multi_stage_ratio(self, standard_solver: ReductionSolver) -> None:
        """Ratio 6:1 requires compound train (e.g. 2:1 * 3:1 = (12T->24T)*(11T->33T))."""
        solutions = standard_solver.solve(target_ratio="6:1", max_solutions=3)
        assert len(solutions) > 0
        for sol in solutions:
            assert sol.achieved_ratio == Fraction(6, 1)
            assert sol.is_approximate is False

        # Verify lowest relative cost is 1.0
        assert solutions[0].relative_cost == 1.0
        # Verify stages are canonically sorted
        for sol in solutions:
            for i in range(len(sol.stages) - 1):
                assert sol.stages[i].pinion <= sol.stages[i + 1].pinion

    def test_uniqueness_no_stage_permutations(self, standard_solver: ReductionSolver) -> None:
        """Ensure no solutions with identical pairs in different orders are returned."""
        solutions = standard_solver.solve(target_ratio="4:1", max_solutions=10)
        seen_keys: set = set()
        for sol in solutions:
            key = sol.canonical_stage_key()
            assert key not in seen_keys, f"Duplicate solution found: {sol}"
            seen_keys.add(key)

    def test_worm_drive_exact_solution(self, standard_solver: ReductionSolver) -> None:
        """With worm drive, ratio 60:1 can be achieved by Worm(30T) * (12T->24T)."""
        solutions = standard_solver.solve(
            target_ratio="60:1", use_worm=True, max_solutions=3
        )
        assert len(solutions) > 0
        for sol in solutions:
            assert sol.achieved_ratio == Fraction(60, 1)
            # Worm stage must be first pair
            first_stage = sol.stages[0]
            assert first_stage.is_worm is True
            assert first_stage.pinion == 1
            assert 11 <= first_stage.gear <= 40

    def test_no_exact_solution_returns_empty_when_approx_disabled(
        self, standard_solver: ReductionSolver
    ) -> None:
        """Ratio 71:1 (71 is a prime > 40) is impossible with spur gears up to 40T."""
        solutions = standard_solver.solve(
            target_ratio="71:1", allow_approximate=False
        )
        assert solutions == []
