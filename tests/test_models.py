"""Unit tests for gear reduction core domain models, costing, and canonical sorting."""

from fractions import Fraction
import pytest

from gear_reduction.core.models import CostModel, GearPair, ReductionSolution


class TestGearPair:
    """Tests for individual mechanical gear pairs."""

    def test_valid_spur_gear_pair(self) -> None:
        pair = GearPair(pinion=12, gear=24)
        assert pair.pinion == 12
        assert pair.gear == 24
        assert pair.is_worm is False
        assert pair.ratio == Fraction(2, 1)
        assert pair.teeth_sum == 36
        assert pair.to_dict() == {"pinion": 12, "gear": 24}

    def test_equal_pinion_and_gear_allowed(self) -> None:
        """A 1:1 stage where pinion equals gear is valid."""
        pair = GearPair(pinion=20, gear=20)
        assert pair.ratio == Fraction(1, 1)
        assert pair.teeth_sum == 40

    def test_pinion_larger_than_gear_rejected(self) -> None:
        """Pinion must be <= gear for speed reduction."""
        with pytest.raises(ValueError, match="must be <= gear tooth count"):
            GearPair(pinion=30, gear=15)

    def test_non_positive_teeth_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive integers"):
            GearPair(pinion=0, gear=20)
        with pytest.raises(ValueError, match="positive integers"):
            GearPair(pinion=12, gear=-5)

    def test_worm_gear_pair(self) -> None:
        worm_pair = GearPair(pinion=1, gear=30, is_worm=True)
        assert worm_pair.pinion == 1
        assert worm_pair.gear == 30
        assert worm_pair.is_worm is True
        assert worm_pair.ratio == Fraction(30, 1)
        assert worm_pair.teeth_sum == 31

    def test_worm_pinion_must_be_one(self) -> None:
        with pytest.raises(ValueError, match="Worm pinion must have 1 tooth"):
            GearPair(pinion=2, gear=30, is_worm=True)


class TestCostModel:
    """Tests for the costing model."""

    def test_single_stage_cost(self) -> None:
        # 12T + 24T = 36 teeth. 1 stage * 50 = 50. Total = 86.
        cm = CostModel(stage_penalty=50)
        stages = [GearPair(12, 24)]
        assert cm.compute_cost(stages) == 86

    def test_two_stage_cost(self) -> None:
        # (12 + 24) + (15 + 30) = 36 + 45 = 81 teeth. 2 stages * 50 = 100. Total = 181.
        cm = CostModel(stage_penalty=50)
        stages = [GearPair(12, 24), GearPair(15, 30)]
        assert cm.compute_cost(stages) == 181

    def test_worm_stage_cost_with_multiplier(self) -> None:
        # Default worm multiplier 3.0: Worm 1T + 3.0 * 30T = 91. Spur: 12T + 24T = 36. Teeth = 127. 2 stages * 50 = 100. Total = 227.
        cm = CostModel(stage_penalty=50, worm_gear_multiplier=3.0)
        stages = [GearPair(1, 30, is_worm=True), GearPair(12, 24)]
        assert cm.compute_cost(stages) == 227

    def test_worm_stage_cost_unweighted(self) -> None:
        # With worm multiplier 1.0: Worm 1T + 30T = 31. Spur: 12T + 24T = 36. Teeth = 67. 2 stages * 50 = 100. Total = 167.
        cm = CostModel(stage_penalty=50, worm_gear_multiplier=1.0)
        stages = [GearPair(1, 30, is_worm=True), GearPair(12, 24)]
        assert cm.compute_cost(stages) == 167



class TestReductionSolution:
    """Tests for canonical ordering, relative cost weighting, and deviation calculation."""

    def test_canonical_sorting_spur_stages(self) -> None:
        """Spur stages must be sorted ascending by pinion tooth count."""
        cm = CostModel()
        stage_a = GearPair(18, 36)
        stage_b = GearPair(12, 24)
        stage_c = GearPair(15, 30)

        # Pass in unordered sequence
        sol = ReductionSolution.create([stage_a, stage_b, stage_c], cm)

        assert sol.stages[0].pinion == 12
        assert sol.stages[1].pinion == 15
        assert sol.stages[2].pinion == 18

    def test_worm_stage_always_first(self) -> None:
        """If a worm stage is present, it must always be the first stage."""
        cm = CostModel()
        spur = GearPair(12, 24)
        worm = GearPair(1, 30, is_worm=True)

        sol = ReductionSolution.create([spur, worm], cm)
        assert sol.stages[0].is_worm is True
        assert sol.stages[0].pinion == 1
        assert sol.stages[0].gear == 30
        assert sol.stages[1].pinion == 12

    def test_uniqueness_canonical_key(self) -> None:
        """Permutations of identical stages must produce identical canonical keys."""
        cm = CostModel()
        sol1 = ReductionSolution.create([GearPair(12, 24), GearPair(15, 30)], cm)
        sol2 = ReductionSolution.create([GearPair(15, 30), GearPair(12, 24)], cm)

        assert sol1.canonical_stage_key() == sol2.canonical_stage_key()
        assert sol1.achieved_ratio == sol2.achieved_ratio
        assert sol1.cost == sol2.cost

    def test_deviation_percentage_formatting(self) -> None:
        """Verifies deviation percentage calculation formula: |(achieved - target) / target| * 100%."""
        cm = CostModel()
        # Target = 10, Achieved = 20 / 2 = 10 -> exact
        sol_exact = ReductionSolution.create(
            [GearPair(12, 24), GearPair(11, 55 if 55 <= 40 else 22)],  # adjust to real
            cm,
            target_ratio=Fraction(4, 1),
        )
        assert sol_exact.is_approximate is False
        assert sol_exact.deviation_percentage is None

        # Target = Fraction(100, 1), Achieved = Fraction(99, 1) -> 1% deviation
        sol_approx = ReductionSolution.create(
            [GearPair(1, 33, is_worm=True), GearPair(11, 33)],
            cm,
            target_ratio=Fraction(100, 1),
        )
        assert sol_approx.is_approximate is True
        assert sol_approx.achieved_ratio == Fraction(99, 1)
        # |99 - 100| / 100 * 100% = 1.00%
        assert sol_approx.deviation_percentage == "1.00%"
