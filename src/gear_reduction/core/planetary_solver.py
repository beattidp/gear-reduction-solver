"""Solver engine for epicyclic (planetary) gear reduction systems.

Engineering Rationale:
---------------------
Planetary gear systems provide compact, high-power-density speed reduction with
coaxial input and output shafts. This solver enumerates physically realizable
planetary stages meeting coaxiality, symmetric assembly, and planet tip clearance,
and solves for single-stage and cascaded multi-stage configurations meeting a target
reduction ratio.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from fractions import Fraction
from typing import Sequence

from .planetary import (
    PlanetaryCostModel,
    PlanetarySolution,
    PlanetaryStage,
    PlanetaryStator,
)


class PlanetarySolver:
    """Calculates optimal single-stage and multi-stage planetary gear reduction configurations."""

    def __init__(
        self,
        available_teeth: Sequence[int],
        cost_model: PlanetaryCostModel | None = None,
        max_stages: int = 3,
        max_ring_teeth: int = 120,
        planets_count: int = 3,
        strict_ring_inventory: bool = False,
    ) -> None:
        """Initializes the planetary solver with tooth inventory and geometric parameters.

        Args:
            available_teeth: Tooth counts available for sun and planet gears (e.g. 11-40).
            cost_model: PlanetaryCostModel instance.
            max_stages: Maximum number of cascaded planetary stages (default: 3).
            max_ring_teeth: Maximum allowable teeth for internal ring gear (default: 120).
            planets_count: Number of planet gears per stage (default: 3).
            strict_ring_inventory: If True, ring gear teeth must also be present in available_teeth.
        """
        self.available_teeth = sorted(list(set(available_teeth)))
        self.cost_model = cost_model or PlanetaryCostModel()
        self.max_stages = max_stages
        self.max_ring_teeth = max_ring_teeth
        self.planets_count = planets_count
        self.strict_ring_inventory = strict_ring_inventory

        # Precompute all valid single-stage planetary configurations
        self._single_stages: list[PlanetaryStage] = self._generate_valid_stages()

    def _generate_valid_stages(self) -> list[PlanetaryStage]:
        """Generates all physically realizable planetary stages meeting engineering constraints."""
        valid_stages: list[PlanetaryStage] = []
        available_set = set(self.available_teeth)

        for s in self.available_teeth:
            for p in self.available_teeth:
                r = s + 2 * p
                if r > self.max_ring_teeth:
                    continue
                if self.strict_ring_inventory and r not in available_set:
                    continue

                for stator in (
                    PlanetaryStator.RING,
                    PlanetaryStator.CARRIER,
                    PlanetaryStator.SUN,
                ):
                    try:
                        stage = PlanetaryStage(
                            sun=s,
                            planet=p,
                            ring=r,
                            stator=stator,
                            planets_count=self.planets_count,
                        )
                        valid_stages.append(stage)
                    except ValueError:
                        # Skip configurations violating assembly or clearance constraints
                        continue

        return valid_stages

    def solve(
        self,
        target_ratio: Fraction,
        stator: PlanetaryStator | str | None = None,
        allow_approximate: bool = False,
        max_solutions: int = 3,
    ) -> list[PlanetarySolution]:
        """Finds optimal planetary gear reduction solutions for a given target ratio.

        Args:
            target_ratio: Target speed reduction ratio (Fraction, must be > 1.0).
            stator: Optional filter by stationary member ('ring', 'carrier', 'sun', or None/'any').
            allow_approximate: If True and no exact solution exists, returns closest approximations.
            max_solutions: Maximum number of solutions to return (default: 3).

        Returns:
            List of PlanetarySolution instances, sorted by relative cost.
        """
        if target_ratio <= 1:
            raise ValueError(f"Target reduction ratio must be > 1.0, got {target_ratio}")

        # Filter single stages by stator if requested
        stator_enum: PlanetaryStator | None = None
        if stator is not None:
            if isinstance(stator, str):
                s_lower = stator.strip().lower()
                if s_lower and s_lower != "any":
                    stator_enum = PlanetaryStator(s_lower)
            elif isinstance(stator, PlanetaryStator):
                stator_enum = stator

        candidate_stages = (
            [s for s in self._single_stages if s.stator == stator_enum]
            if stator_enum is not None
            else self._single_stages
        )

        if not candidate_stages:
            return []

        # 1. Search for exact solutions at minimal stage depth
        exact_solutions: list[PlanetarySolution] = []
        for depth in range(1, self.max_stages + 1):
            solutions_at_depth = self._search_exact_depth(
                candidate_stages, target_ratio, depth
            )
            if solutions_at_depth:
                exact_solutions.extend(solutions_at_depth)
                # Terminate stage search once minimal stage exact solutions are found
                break

        if exact_solutions:
            return self._rank_solutions(exact_solutions, max_solutions)

        # 2. Approximate search if enabled and no exact solution found
        if allow_approximate:
            approx_solutions = self._search_approximate(
                candidate_stages, target_ratio, self.max_stages, max_candidates=50
            )
            if approx_solutions:
                return self._rank_solutions(approx_solutions, max_solutions)

        return []

    def _search_exact_depth(
        self,
        stages: list[PlanetaryStage],
        target_ratio: Fraction,
        depth: int,
    ) -> list[PlanetarySolution]:
        """Searches for exact solutions at a specific stage depth."""
        solutions: list[PlanetarySolution] = []

        if depth == 1:
            for s in stages:
                if s.ratio == target_ratio:
                    sol = PlanetarySolution.create(
                        stages=[s],
                        cost_model=self.cost_model,
                        target_ratio=target_ratio,
                    )
                    solutions.append(sol)
            return solutions

        if depth == 2:
            # Map single stages by ratio for Meet-in-the-Middle O(N) lookup
            ratio_map: dict[Fraction, list[PlanetaryStage]] = defaultdict(list)
            for s in stages:
                ratio_map[s.ratio].append(s)

            seen_keys: set[tuple[Any, ...]] = set()
            for s1 in stages:
                needed = target_ratio / s1.ratio
                if needed in ratio_map:
                    for s2 in ratio_map[needed]:
                        sol = PlanetarySolution.create(
                            stages=[s1, s2],
                            cost_model=self.cost_model,
                            target_ratio=target_ratio,
                        )
                        key = sol.canonical_stage_key()
                        if key not in seen_keys:
                            seen_keys.add(key)
                            solutions.append(sol)
            return solutions

        # For depth >= 3: recursive branch and bound
        return self._search_exact_recursive(stages, target_ratio, depth)

    def _search_exact_recursive(
        self,
        stages: list[PlanetaryStage],
        target_ratio: Fraction,
        depth: int,
    ) -> list[PlanetarySolution]:
        """Recursive search with ratio pruning for depth >= 3."""
        solutions: list[PlanetarySolution] = []
        seen_keys: set[tuple[Any, ...]] = set()

        min_ratio = min(s.ratio for s in stages)
        max_ratio = max(s.ratio for s in stages)

        def backtrack(current_stages: list[PlanetaryStage], remaining_ratio: Fraction) -> None:
            rem_depth = depth - len(current_stages)
            if rem_depth == 1:
                for s in stages:
                    if s.ratio == remaining_ratio:
                        sol = PlanetarySolution.create(
                            stages=current_stages + [s],
                            cost_model=self.cost_model,
                            target_ratio=target_ratio,
                        )
                        key = sol.canonical_stage_key()
                        if key not in seen_keys:
                            seen_keys.add(key)
                            solutions.append(sol)
                return

            # Prune if remaining ratio cannot be reached within theoretical bounds
            if remaining_ratio < (min_ratio ** rem_depth) or remaining_ratio > (max_ratio ** rem_depth):
                return

            for s in stages:
                backtrack(current_stages + [s], remaining_ratio / s.ratio)

        backtrack([], target_ratio)
        return solutions

    def _search_approximate(
        self,
        stages: list[PlanetaryStage],
        target_ratio: Fraction,
        max_depth: int,
        max_candidates: int = 50,
    ) -> list[PlanetarySolution]:
        """Finds closest approximate planetary solutions within allowed stage depth."""
        # Max-heap keeping the best max_candidates closest ratios
        # Heap elements: (-deviation, cost, solution)
        target_float = float(target_ratio)
        heap: list[tuple[float, int, int, PlanetarySolution]] = []
        seen_keys: set[tuple[Any, ...]] = set()
        counter = 0

        def evaluate(current_stages: list[PlanetaryStage]) -> None:
            nonlocal counter
            sol = PlanetarySolution.create(
                stages=current_stages,
                cost_model=self.cost_model,
                target_ratio=target_ratio,
            )
            key = sol.canonical_stage_key()
            if key in seen_keys:
                return
            seen_keys.add(key)

            achieved_float = float(sol.achieved_ratio)
            dev = abs(achieved_float - target_float) / target_float
            # Only consider reasonably close approximations (within 20%)
            if dev > 0.20:
                return

            counter += 1
            item = (-dev, -sol.cost, counter, sol)
            if len(heap) < max_candidates:
                heapq.heappush(heap, item)
            else:
                if item > heap[0]:
                    heapq.heapreplace(heap, item)

        # Evaluate 1-stage
        for s in stages:
            evaluate([s])

        # Evaluate 2-stage
        if max_depth >= 2:
            for s1 in stages:
                for s2 in stages:
                    evaluate([s1, s2])

        # Evaluate 3-stage if max_depth >= 3
        if max_depth >= 3:
            for s1 in stages:
                for s2 in stages:
                    r12 = s1.ratio * s2.ratio
                    if abs(float(r12) - target_float) / target_float < 0.20:
                        evaluate([s1, s2])
                    else:
                        for s3 in stages:
                            r123 = r12 * s3.ratio
                            if abs(float(r123) - target_float) / target_float < 0.15:
                                evaluate([s1, s2, s3])

        return [item[3] for item in heap]

    def _rank_solutions(
        self,
        solutions: list[PlanetarySolution],
        max_solutions: int,
    ) -> list[PlanetarySolution]:
        """Ranks, normalizes relative costs, and selects top unique planetary solutions."""
        if not solutions:
            return []

        # Deduplicate identical canonical stage keys
        unique_map: dict[tuple[Any, ...], PlanetarySolution] = {}
        for sol in solutions:
            key = sol.canonical_stage_key()
            if key not in unique_map:
                unique_map[key] = sol
            else:
                # Prefer solutions with superior torque progression
                existing_pen = unique_map[key].progression_penalty()
                sol_pen = sol.progression_penalty()
                if sol_pen < existing_pen:
                    unique_map[key] = sol

        unique_solutions = list(unique_map.values())

        # Sort primarily by:
        # 1. Deviation percentage (for approximate solutions)
        # 2. Cost (lowest first)
        # 3. Progression penalty (smoother torque flow)
        unique_solutions.sort(
            key=lambda s: (
                abs(float(s.achieved_ratio - s.achieved_ratio))
                if not s.is_approximate
                else float(s.deviation_percentage.replace("%", "")) if s.deviation_percentage else 0.0,
                s.cost,
                s.progression_penalty(),
            )
        )

        selected = unique_solutions[:max_solutions]
        if selected:
            min_cost = selected[0].cost
            for sol in selected:
                sol.relative_cost = round(sol.cost / min_cost, 4)

        return selected
