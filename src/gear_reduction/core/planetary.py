"""Domain models representing epicyclic (planetary) gear stages, configurations, and cost models.

Engineering Rationale:
---------------------
An epicyclic (planetary) gear stage consists of four primary components:
1. Sun gear (S): A central external spur gear.
2. Planet gears (P): N identical external spur gears mounted on pins on a carrier.
3. Outer Ring / Annulus gear (R): An internal gear meshing with all planet gears.
4. Planet Carrier (C): The rotating arm holding the planet gears in orbit.

Fundamental Willis Equation:
---------------------------
The kinematic relationship between angular velocities is:
    S * omega_S + R * omega_R - (S + R) * omega_C = 0

Depending on which member is held stationary (the stator), the stage provides
three canonical speed reduction configurations (where Reduction Ratio = omega_in / omega_out > 1.0):

1. Ring Stator (omega_R = 0):
   - Input = Sun (omega_in = omega_S), Output = Carrier (omega_out = omega_C)
   - Ratio: (S + R) / S = 1 + R / S  (Forward rotation, Ratio > 2.0)
2. Carrier Stator (omega_C = 0, stationary planet pins):
   - Input = Sun (omega_in = omega_S), Output = Ring (omega_out = omega_R)
   - Ratio: R / S  (Inverted / reverse rotation, Ratio > 1.0)
3. Sun Stator (omega_S = 0):
   - Input = Ring (omega_in = omega_R), Output = Carrier (omega_out = omega_C)
   - Ratio: (S + R) / R = 1 + S / R  (Forward rotation, 1.0 < Ratio < 2.0)

Mechanical & Geometric Assembly Constraints:
--------------------------------------------
1. Coaxiality Condition:
   The center distance between sun and planets must match the internal pitch radius
   of the ring gear:
       R = S + 2 * P
   Hence, R > S, and (R - S) must be an even integer: P = (R - S) / 2.

2. Assembly / Symmetrical Meshing Condition:
   For N planets symmetrically distributed at 360 / N degrees:
       (S + R) % N == 0  <=>  (2*S + 2*P) % N == 0

3. Adjacent Planet Tip Clearance:
   The planets orbit at radius r = (S + P) / 2. The straight-line distance between
   adjacent planet centers must exceed the planet gear outer diameter (P + 2):
       (S + P) * sin(pi / N) > P + 2
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any, Sequence


class PlanetaryStator(str, Enum):
    """Specifies the stationary component in an epicyclic gear stage."""

    RING = "ring"
    CARRIER = "carrier"
    SUN = "sun"


@dataclass(frozen=True, slots=True)
class PlanetaryStage:
    """Represents a single epicyclic (planetary) gear stage.

    Attributes:
        sun: Tooth count of the sun gear.
        planet: Tooth count of each planet gear.
        ring: Tooth count of the internal ring gear.
        stator: The stationary member (RING, CARRIER, or SUN).
        planets_count: Number of planet gears mounted on the carrier (default: 3).
    """

    sun: int
    planet: int
    ring: int
    stator: PlanetaryStator
    planets_count: int = 3

    def __post_init__(self) -> None:
        """Validates mechanical, assembly, and geometric clearance constraints.

        Raises:
            ValueError: If tooth counts are invalid, or if coaxiality, assembly,
                or clearance conditions are violated.
        """
        if self.sun <= 0 or self.planet <= 0 or self.ring <= 0:
            raise ValueError(
                f"Gear teeth must be positive integers: sun={self.sun}, planet={self.planet}, ring={self.ring}"
            )
        if self.planets_count < 2:
            raise ValueError(
                f"Planets count must be at least 2 for balanced epicyclic gearing, got {self.planets_count}"
            )

        # 1. Coaxiality constraint: R = S + 2*P
        if self.ring != self.sun + 2 * self.planet:
            raise ValueError(
                f"Coaxiality constraint violated: ring ({self.ring}) != sun ({self.sun}) + 2 * planet ({self.planet})"
            )

        # 2. Assembly condition: (S + R) % N == 0
        if (self.sun + self.ring) % self.planets_count != 0:
            raise ValueError(
                f"Assembly condition violated: (sun + ring) = {self.sun + self.ring} is not divisible by "
                f"planets_count ({self.planets_count})"
            )

        # 3. Adjacent planet tip clearance condition: (S + P) * sin(pi / N) > P + 2
        d_centers = (self.sun + self.planet) * math.sin(math.pi / self.planets_count)
        d_outer = self.planet + 2
        if d_centers <= d_outer:
            raise ValueError(
                f"Adjacent planet clearance condition violated: center distance {d_centers:.2f} <= outer diameter {d_outer}"
            )

    @property
    def input_element(self) -> str:
        """Identifies the mechanical input element for speed reduction."""
        if self.stator == PlanetaryStator.RING:
            return "sun"
        elif self.stator == PlanetaryStator.CARRIER:
            return "sun"
        else:  # SUN
            return "ring"

    @property
    def output_element(self) -> str:
        """Identifies the mechanical output element for speed reduction."""
        if self.stator == PlanetaryStator.RING:
            return "carrier"
        elif self.stator == PlanetaryStator.CARRIER:
            return "ring"
        else:  # SUN
            return "carrier"

    @property
    def is_inverted(self) -> bool:
        """Returns True if the output rotation is opposite to the input rotation.

        Only the CARRIER stator configuration (with stationary planet pins)
        inverts output direction (acts like a spur idler mesh).
        """
        return self.stator == PlanetaryStator.CARRIER

    @property
    def ratio(self) -> Fraction:
        """Computes the exact rational speed reduction ratio (omega_in / omega_out).

        Formulas:
        - RING stator: (S + R) / S = 1 + R / S
        - CARRIER stator: R / S
        - SUN stator: (S + R) / R = 1 + S / R
        """
        if self.stator == PlanetaryStator.RING:
            return Fraction(self.sun + self.ring, self.sun)
        elif self.stator == PlanetaryStator.CARRIER:
            return Fraction(self.ring, self.sun)
        else:  # SUN
            return Fraction(self.sun + self.ring, self.ring)

    def to_dict(self) -> dict[str, Any]:
        """Serializes stage to a structured dictionary."""
        return {
            "sun": self.sun,
            "planet": self.planet,
            "ring": self.ring,
            "planets_count": self.planets_count,
            "stator": self.stator.value,
            "input": self.input_element,
            "output": self.output_element,
            "ratio": f"{self.ratio.numerator}/{self.ratio.denominator}",
            "is_inverted": self.is_inverted,
        }

    def __repr__(self) -> str:
        inv = " [Inverted]" if self.is_inverted else ""
        return (
            f"PlanetaryStage(Stator={self.stator.value.title()}, S={self.sun}T, "
            f"P={self.planet}Tx{self.planets_count}, R={self.ring}T, "
            f"ratio={self.ratio.numerator}/{self.ratio.denominator}{inv})"
        )


@dataclass(frozen=True, slots=True)
class PlanetaryCostModel:
    """Calculates fabrication, material, and assembly cost for planetary stages.

    Engineering Rationale:
    ---------------------
    A planetary stage requires:
    - 1 Sun gear (external spur, teeth = S)
    - N Planet gears (external spurs, teeth = N * P)
    - 1 Ring gear (internal gear, teeth = R). Internal gears require internal slotting
      or specialized shaper cutting, typically carrying a cost premium of ~1.5x.
    - Carrier / pin assembly: Machining precision planetary carrier plates, ground hardened
      pins, and needle roller bearings justifies a stage penalty (default: 60).

    Attributes:
        ring_multiplier: Weighting factor for internal ring gear teeth (default: 1.5).
        stage_penalty: Flat penalty added per planetary stage for carrier and bearings (default: 60).
        teeth_multiplier: Global scaling factor for teeth count sum (default: 1.0).
    """

    ring_multiplier: float = 1.5
    stage_penalty: int = 60
    teeth_multiplier: float = 1.0

    def compute_cost(self, stages: Sequence[PlanetaryStage]) -> int:
        """Calculates the absolute integer cost for a sequence of planetary stages."""
        teeth_cost = 0.0
        for stage in stages:
            sun_cost = stage.sun * self.teeth_multiplier
            planets_cost = (stage.planets_count * stage.planet) * self.teeth_multiplier
            ring_cost = (stage.ring * self.ring_multiplier) * self.teeth_multiplier
            teeth_cost += sun_cost + planets_cost + ring_cost

        stages_penalty = self.stage_penalty * len(stages)
        return int(round(teeth_cost)) + stages_penalty


@dataclass(slots=True)
class PlanetarySolution:
    """Represents a complete planetary reduction solution (single or cascaded stages).

    Attributes:
        stages: Ordered sequence of planetary stages.
        achieved_ratio: Exact rational reduction ratio achieved.
        cost: Absolute integer fabrication and assembly cost.
        relative_cost: Relative cost weight normalized to lowest-cost solution (lowest = 1.0).
        is_approximate: True if achieved ratio deviates from the user's target ratio.
        deviation_percentage: Formatted string (e.g. '0.50%') indicating deviation from target.
    """

    stages: tuple[PlanetaryStage, ...]
    achieved_ratio: Fraction
    cost: int
    relative_cost: float = 1.0
    is_approximate: bool = False
    deviation_percentage: str | None = None

    @classmethod
    def create(
        cls,
        stages: Sequence[PlanetaryStage],
        cost_model: PlanetaryCostModel,
        target_ratio: Fraction | None = None,
    ) -> PlanetarySolution:
        """Factory method to construct a canonical PlanetarySolution."""
        canonical_stages = tuple(stages)
        total_ratio = Fraction(1, 1)
        for stage in canonical_stages:
            total_ratio *= stage.ratio

        cost = cost_model.compute_cost(canonical_stages)

        is_approx = False
        deviation_str: str | None = None
        if target_ratio is not None and total_ratio != target_ratio:
            is_approx = True
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

    def canonical_stage_key(self) -> tuple[tuple[int, int, int, str, int], ...]:
        """Returns a hashable signature representing the planetary stages."""
        return tuple(
            sorted(
                (s.sun, s.planet, s.ring, s.stator.value, s.planets_count)
                for s in self.stages
            )
        )

    def progression_penalty(self) -> tuple[int, float]:
        """Evaluates torque progression across cascaded planetary stages."""
        if len(self.stages) <= 1:
            return (0, 0.0)

        inversions = 0
        ratio_penalty = 0.0
        for i in range(len(self.stages) - 1):
            if self.stages[i].ring > self.stages[i + 1].ring:
                inversions += 1
            r1 = float(self.stages[i].ratio)
            r2 = float(self.stages[i + 1].ratio)
            if r1 > r2:
                ratio_penalty += (r1 - r2)

        return (inversions, ratio_penalty)

    @property
    def is_inverted(self) -> bool:
        """Returns True if the composite train inverts output direction.

        An odd number of inverted stages yields net inversion.
        """
        inverted_stages = sum(1 for s in self.stages if s.is_inverted)
        return (inverted_stages % 2) == 1

    def to_dict(self) -> dict[str, Any]:
        """Serializes solution to standard JSON format."""
        achieved_float = float(self.achieved_ratio)
        data: dict[str, Any] = {
            "type": "planetary",
            "stages": [s.to_dict() for s in self.stages],
            "achieved_ratio_fraction": f"{self.achieved_ratio.numerator}/{self.achieved_ratio.denominator}",
            "achieved_ratio": round(achieved_float, 6),
            "cost": self.cost,
            "relative_cost": round(self.relative_cost, 4),
            "is_approximate": self.is_approximate,
            "is_inverted": self.is_inverted,
        }
        if self.deviation_percentage is not None:
            data["deviation_percentage"] = self.deviation_percentage
        return data
