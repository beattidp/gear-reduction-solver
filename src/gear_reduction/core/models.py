"""Domain models representing mechanical gear pairs, multi-stage trains, and cost evaluations.

Engineering Rationale:
---------------------
In compound gear train design, mechanical speed reduction is achieved by cascading
successive meshed gear stages. Each stage consists of a driving pinion (P) and a
driven gear (G). For standard speed reduction, P <= G, yielding a reduction ratio
R_stage = G / P >= 1.0.

When a worm drive is used as the input stage, the single-start worm acts as a 1-tooth
pinion meshing with a standard spur/worm wheel, yielding R_worm = G_worm / 1 = G_worm.

To avoid numerical floating-point inaccuracies during exact factorization, reduction
ratios are represented internally using rational fractions (`fractions.Fraction`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class GearPair:
    """Represents a single reduction stage consisting of a driving pinion and driven gear.

    Attributes:
        pinion: Tooth count of the driving pinion gear (1 for a single-start worm).
        gear: Tooth count of the driven gear.
        is_worm: True if this stage is driven by a worm screw (pinion = 1).
    """

    pinion: int
    gear: int
    is_worm: bool = False

    def __post_init__(self) -> None:
        """Validates mechanical meshing constraints.

        Raises:
            ValueError: If tooth counts are non-positive, or if a non-worm pinion
                exceeds the driven gear tooth count (pinion > gear).
        """
        if self.pinion <= 0 or self.gear <= 0:
            raise ValueError(
                f"Gear teeth must be positive integers: pinion={self.pinion}, gear={self.gear}"
            )
        if self.is_worm and self.pinion != 1:
            raise ValueError(f"Worm pinion must have 1 tooth, received {self.pinion}")
        if not self.is_worm and self.pinion > self.gear:
            raise ValueError(
                f"Pinion tooth count ({self.pinion}) must be <= gear tooth count ({self.gear}) "
                "for speed reduction."
            )

    @property
    def ratio(self) -> Fraction:
        """Calculates exact rational reduction ratio G / P."""
        return Fraction(self.gear, self.pinion)

    @property
    def teeth_sum(self) -> int:
        """Returns the total number of teeth in this stage (used for cost calculation)."""
        return self.pinion + self.gear

    def to_dict(self) -> dict[str, int]:
        """Serializes stage pair to dictionary format conforming to requirements."""
        return {"pinion": self.pinion, "gear": self.gear}

    def __repr__(self) -> str:
        if self.is_worm:
            return f"GearPair(Worm: 1T -> {self.gear}T, ratio={self.gear}:1)"
        return f"GearPair({self.pinion}T -> {self.gear}T, ratio={self.gear}/{self.pinion})"


@dataclass(frozen=True, slots=True)
class CostModel:
    """Calculates mechanical fabrication and assembly cost for a gear train.

    Costing Model Specification:
    ----------------------------
    The cost of a solution is calculated by the sum of teeth of all gears used,
    plus a penalty of 50 for each gear pair (stage) in the train:
        Cost = sum(teeth_cost) + (50 * stage_count)

    Engineering Rationale for Worm Gear Weighting:
    ----------------------------------------------
    Worm wheels (gears) typically require specialty bronze alloys (e.g. SAE 65)
    to prevent galling against steel worm screws, require specialized throated hobbing,
    and enlarge gearbox envelope sizes. Therefore, worm wheel teeth are weighted by
    `worm_gear_multiplier` (default: 3.0x) so that smaller worm gears are naturally
    favored in relative cost calculations.

    Attributes:
        stage_penalty: Flat penalty added per stage to penalize excessive stages/shafts.
        teeth_multiplier: Scaling factor for teeth count sum (default 1.0).
        worm_gear_multiplier: Cost multiplier for worm wheel teeth (default 3.0).
    """

    stage_penalty: int = 50
    teeth_multiplier: float = 1.0
    worm_gear_multiplier: float = 3.0

    def compute_cost(self, stages: Sequence[GearPair]) -> int:
        """Calculates the absolute integer cost for a given sequence of gear pairs."""
        teeth_cost = 0.0
        for stage in stages:
            if stage.is_worm:
                teeth_cost += stage.pinion + (self.worm_gear_multiplier * stage.gear)
            else:
                teeth_cost += (stage.pinion + stage.gear) * self.teeth_multiplier

        stages_penalty = self.stage_penalty * len(stages)
        return int(round(teeth_cost)) + stages_penalty


@dataclass(slots=True)
class ReductionSolution:
    """Represents a complete compound gear train solution meeting or approximating a target ratio.

    Attributes:
        stages: Ordered sequence of gear pairs.
        achieved_ratio: Exact rational reduction ratio achieved by cascading stages.
        cost: Absolute integer cost computed by CostModel.
        relative_cost: Relative cost weight normalized to lowest-cost solution (lowest = 1.0).
        is_approximate: True if achieved ratio deviates from the user's target ratio.
        deviation_percentage: Formatted string (e.g. '0.52%') indicating deviation from target.
    """

    stages: tuple[GearPair, ...]
    achieved_ratio: Fraction
    cost: int
    relative_cost: float = 1.0
    is_approximate: bool = False
    deviation_percentage: str | None = None

    @classmethod
    def create(
        cls,
        stages: Sequence[GearPair],
        cost_model: CostModel,
        target_ratio: Fraction | None = None,
    ) -> ReductionSolution:
        """Factory method to construct a canonical ReductionSolution.

        Enforces Canonical Ordering:
        ----------------------------
        1. If a worm stage is present, it must always be the first pair (index 0).
        2. All subsequent spur stages are sorted ascending by pinion tooth count
           (breaking ties by gear tooth count).
        3. Computes the composite reduction ratio R = product(stage.ratio).
        4. Calculates deviation percentage if target_ratio is provided and differs.
        """
        worm_stages = [s for s in stages if s.is_worm]
        spur_stages = [s for s in stages if not s.is_worm]

        if len(worm_stages) > 1:
            raise ValueError("Only a single initial worm drive stage is supported.")

        # Sort spur stages canonically by (pinion, gear)
        sorted_spurs = sorted(spur_stages, key=lambda p: (p.pinion, p.gear))
        canonical_stages = tuple(worm_stages + sorted_spurs)

        # Compute composite ratio R = product of individual stage ratios
        total_ratio = Fraction(1, 1)
        for stage in canonical_stages:
            total_ratio *= stage.ratio

        cost = cost_model.compute_cost(canonical_stages)

        is_approx = False
        deviation_str: str | None = None
        if target_ratio is not None and total_ratio != target_ratio:
            is_approx = True
            # Deviation percentage = |(achievedRatio - targetRatio) / targetRatio| * 100
            diff = abs(float(total_ratio - target_ratio))
            target_float = float(target_ratio)
            dev_val = (diff / target_float) * 100.0
            deviation_str = f"{dev_val:.2f}%"

        return cls(
            stages=canonical_stages,
            achieved_ratio=total_ratio,
            cost=cost,
            relative_cost=1.0,
            is_approximate=is_approx,
            deviation_percentage=deviation_str,
        )

    def canonical_stage_key(self) -> tuple[tuple[int, int, bool], ...]:
        """Returns a hashable signature representing the unordered multiset of stages.

        Because stage order is mathematically commutative for total ratio, any train
        with identical stages (e.g. [(12, 24), (15, 30)] vs [(15, 30), (12, 24)])
        is physically equivalent. The canonical key ensures strict uniqueness.
        """
        worm_keys = tuple(
            (s.pinion, s.gear, s.is_worm) for s in self.stages if s.is_worm
        )
        spur_keys = tuple(
            sorted(
                (s.pinion, s.gear, s.is_worm) for s in self.stages if not s.is_worm
            )
        )
        return worm_keys + spur_keys

    def canonical_parts_key(self) -> tuple[int | None, tuple[int, ...], tuple[int, ...]]:
        """Returns a hashable signature representing the physical multiset of gears required.

        Engineering Rationale:
        ---------------------
        Any solution that requires the exact same physical gear inventory
        (e.g. pinions {11, 12} and gears {33, 40}) is physically equivalent in bill of materials.
        To avoid cluttering results with identical parts permutations, solutions sharing the same
        parts signature are deduplicated, keeping only the optimal progressive torque arrangement.
        """
        worm_gears = tuple(s.gear for s in self.stages if s.is_worm)
        worm_wheel = worm_gears[0] if worm_gears else None
        spur_pinions = tuple(sorted(s.pinion for s in self.stages if not s.is_worm))
        spur_gears = tuple(sorted(s.gear for s in self.stages if not s.is_worm))
        return (worm_wheel, spur_pinions, spur_gears)

    def progression_penalty(self) -> tuple[int, float]:
        """Scores how well the stages follow mechanical torque progression.

        In a speed reducer, torque increases at each subsequent stage:
            Torque_out = Torque_in * R_stage
        Mechanical guidelines favor:
        1. Non-decreasing driven gear sizes (G_1 <= G_2 <= ...) to withstand higher tangential tooth load.
        2. Non-decreasing pinion sizes (P_1 <= P_2 <= ...).

        Returns:
            (inversion_count, ratio_decrease_penalty)
            Lower values indicate superior mechanical progression.
        """
        spur_stages = [s for s in self.stages if not s.is_worm]
        if len(spur_stages) <= 1:
            return (0, 0.0)

        inversions = 0
        ratio_penalty = 0.0
        for i in range(len(spur_stages) - 1):
            if spur_stages[i].gear > spur_stages[i + 1].gear:
                inversions += 1
            r1 = float(spur_stages[i].ratio)
            r2 = float(spur_stages[i + 1].ratio)
            if r1 > r2:
                ratio_penalty += (r1 - r2)

        return (inversions, ratio_penalty)


    def to_dict(self) -> dict[str, Any]:
        """Serializes solution to standard JSON-compatible dictionary."""
        achieved_float = float(self.achieved_ratio)
        data: dict[str, Any] = {
            "stages": [s.to_dict() for s in self.stages],
            "achieved_ratio_fraction": f"{self.achieved_ratio.numerator}/{self.achieved_ratio.denominator}",
            "achieved_ratio": round(achieved_float, 6),
            "cost": self.cost,
            "relative_cost": round(self.relative_cost, 4),
            "is_approximate": self.is_approximate,
        }
        if self.deviation_percentage is not None:
            data["deviation_percentage"] = self.deviation_percentage
        return data


# Type alias providing semantic equivalence between GearTrain and ReductionSolution
GearTrain = ReductionSolution

