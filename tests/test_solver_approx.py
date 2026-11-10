"""Unit tests for approximate gear reduction solving."""

from fractions import Fraction
import pytest

from gear_reduction.core.solver import ReductionSolver


class TestApproximateSolver:
    """Tests for approximate solution mode, deviation percentages, and cost ranking."""

    @pytest.fixture
    def standard_solver(self) -> ReductionSolver:
        return ReductionSolver(available_teeth=list(range(11, 41)))

    def test_approximate_solution_for_prime_ratio(
        self, standard_solver: ReductionSolver
    ) -> None:
        """Ratio 71:1 has no exact solution with 11-40T spur gears (71 is prime > 40).

        When approximate solutions are allowed, the solver must return solutions
        with achievedRatio as CLOSE as possible to targetRatio, and compute deviationPercentage.
        """
        target = "71:1"
        solutions = standard_solver.solve(
            target_ratio=target, allow_approximate=True, max_solutions=3
        )
        assert len(solutions) > 0
        for sol in solutions:
            assert sol.is_approximate is True
            assert sol.deviation_percentage is not None
            assert sol.deviation_percentage.endswith("%")

            # Validate deviation percentage formula: |achieved - target| / target * 100
            target_float = 71.0
            achieved_float = float(sol.achieved_ratio)
            expected_dev = (abs(achieved_float - target_float) / target_float) * 100.0
            actual_dev = float(sol.deviation_percentage.rstrip("%"))
            assert abs(actual_dev - expected_dev) < 0.05

        # Verify relative cost weight normalization: lowest cost is 1.0
        assert solutions[0].relative_cost == 1.0
        for i in range(len(solutions) - 1):
            assert solutions[i].relative_cost <= solutions[i + 1].relative_cost

    def test_approximate_worm_drive(self, standard_solver: ReductionSolver) -> None:
        """High reduction ratio 137:1 with worm drive in approximate mode (137 is prime > 40)."""
        solutions = standard_solver.solve(
            target_ratio="137:1",
            use_worm=True,
            allow_approximate=True,
            max_solutions=3,
        )
        assert len(solutions) > 0
        for sol in solutions:
            assert sol.stages[0].is_worm is True
            assert sol.is_approximate is True
            assert sol.deviation_percentage is not None
            dev_val = float(sol.deviation_percentage.rstrip("%"))
            assert dev_val < 5.0  # Should be within 5% of target

