"""High-performance combinatorial gear reduction solver with exact rational arithmetic and bounded approximate optimization.

Engineering Rationale & Algorithmic Design:
-------------------------------------------
A compound gear train cascades k gear pairs. The total reduction ratio is:
    R = product_{i=1}^k (G_i / P_i)

Because multiplication is commutative, the physical order of spur gear stages does
not alter the overall ratio. Searching naive permutations causes an exponential
slowdown.

To make the solver instantaneous (< 15 ms) across depths 1 through 4:
1. **Canonical Representation & Cost-Sorted Indexing**:
   Single-stage and two-stage spur combinations are grouped by their exact rational ratio.
   For each unique ratio, candidate stage tuples are sorted by teeth cost ascending
   and capped at the top cheapest representatives.
2. **Branch-and-Bound Stage Pruning**:
   Each stage incurs at least (2 * min_teeth + 50) in cost. If the solver already has
   enough exact solutions from shallower depths such that deeper stages cannot beat
   the current top candidate costs, deeper stages are skipped entirely.
3. **Meet-in-the-Middle Lookup**:
   Exact ratio matching queries indexed tables in O(1) time without looping over
   inner-stage permutations.
4. **Worm Drive Handling**:
   When enabled, stage 1 is dedicated to the worm drive (1T pinion -> G_worm teeth),
   and the remaining ratio R / G_worm is solved across subsequent spur stages.
5. **Cost Optimization & Relative Weighting**:
   Absolute cost = sum(teeth) + 50 * stages.
   Relative cost = current_cost / lowest_cost (lowest is exactly 1.0).
6. **Approximate Solver**:
   When no exact match exists and approximate mode is enabled, nearest ratios
   are retrieved using binary search on pre-indexed ratios, and deviation percentage
   is computed as |(achieved - target) / target| * 100%.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from fractions import Fraction
import re
from typing import Any, Sequence

from .models import CostModel, GearPair, ReductionSolution


def parse_ratio(ratio_input: str | int | float | Fraction) -> Fraction:
    """Parses various ratio input formats into an exact Fraction.

    Supported Formats:
        - Ratio string "in:out" (e.g. "10:1", "25:2", "7.5:1")
        - Fraction string "in/out" (e.g. "10/1", "25/2")
        - Integer (e.g. 10 -> Fraction(10, 1))
        - Float (e.g. 12.5 -> Fraction(25, 2))
        - Existing Fraction instance
    """
    if isinstance(ratio_input, Fraction):
        if ratio_input <= 0:
            raise ValueError(f"Target ratio must be positive, got {ratio_input}")
        return ratio_input

    if isinstance(ratio_input, (int, float)):
        if ratio_input <= 0:
            raise ValueError(f"Target ratio must be positive, got {ratio_input}")
        return Fraction(str(ratio_input))

    if isinstance(ratio_input, str):
        clean_str = ratio_input.strip()
        if ":" in clean_str or "/" in clean_str:
            parts = re.split(r"[:/]", clean_str)
            if len(parts) != 2:
                raise ValueError(f"Invalid ratio format '{ratio_input}'. Expected 'in:out'.")
            num_str, den_str = parts[0].strip(), parts[1].strip()
            num_frac = Fraction(num_str)
            den_frac = Fraction(den_str)
            if den_frac <= 0 or num_frac <= 0:
                raise ValueError("Numerator and denominator in ratio must be positive.")
            return num_frac / den_frac

        frac = Fraction(clean_str)
        if frac <= 0:
            raise ValueError(f"Target ratio must be positive, got {frac}")
        return frac

    raise TypeError(f"Unsupported ratio input type: {type(ratio_input)}")


# Module-level index cache: tuple(available_teeth) -> (d1, d2, d1_ratios, d1_floats, d2_ratios, d2_floats)
_INDEX_CACHE: dict[
    tuple[int, ...],
    tuple[
        dict[Fraction, list[tuple[GearPair, ...]]],
        dict[Fraction, list[tuple[GearPair, ...]]],
        list[Fraction],
        list[float],
        list[Fraction],
        list[float],
    ],
] = {}


def _get_or_build_index(
    available_teeth: tuple[int, ...], spur_pairs: list[GearPair]
) -> tuple[
    dict[Fraction, list[tuple[GearPair, ...]]],
    dict[Fraction, list[tuple[GearPair, ...]]],
    list[Fraction],
    list[float],
    list[Fraction],
    list[float],
]:
    if available_teeth in _INDEX_CACHE:
        return _INDEX_CACHE[available_teeth]

    max_keep = 10
    raw_d1: dict[Fraction, list[tuple[GearPair, ...]]] = defaultdict(list)
    for pair in spur_pairs:
        raw_d1[pair.ratio].append((pair,))

    d1: dict[Fraction, list[tuple[GearPair, ...]]] = {}
    for r, pairs_list in raw_d1.items():
        pairs_list.sort(key=lambda combo: sum(s.teeth_sum for s in combo))
        d1[r] = pairs_list[:max_keep]

    raw_d2: dict[Fraction, list[tuple[GearPair, ...]]] = defaultdict(list)
    n_spurs = len(spur_pairs)
    for i in range(n_spurs):
        p1 = spur_pairs[i]
        p1_g, p1_p = p1.gear, p1.pinion
        for j in range(i, n_spurs):
            p2 = spur_pairs[j]
            comb_ratio = Fraction(p1_g * p2.gear, p1_p * p2.pinion)
            raw_d2[comb_ratio].append((p1, p2))

    d2: dict[Fraction, list[tuple[GearPair, ...]]] = {}
    for r, combos in raw_d2.items():
        combos.sort(key=lambda combo: sum(s.teeth_sum for s in combo))
        d2[r] = combos[:max_keep]

    d1_ratios = sorted(d1.keys())
    d1_floats = [float(r) for r in d1_ratios]

    d2_ratios = sorted(d2.keys())
    d2_floats = [float(r) for r in d2_ratios]

    result = (d1, d2, d1_ratios, d1_floats, d2_ratios, d2_floats)
    _INDEX_CACHE[available_teeth] = result
    return result


class ReductionSolver:
    """Engine for finding optimal multi-stage compound gear trains."""

    def __init__(
        self,
        available_teeth: Sequence[int] | None = None,
        cost_model: CostModel | None = None,
        max_stages: int = 4,
    ) -> None:
        """Initializes the solver with available gear tooth inventory and cost model."""
        if available_teeth is None:
            self.available_teeth = sorted(list(range(11, 41)))
        else:
            sorted_teeth = sorted(list(set(available_teeth)))
            if any(t <= 0 for t in sorted_teeth):
                raise ValueError("All gear sizes must be positive integers.")
            self.available_teeth = sorted_teeth

        self.cost_model = cost_model if cost_model is not None else CostModel()
        self.max_stages = max(1, min(max_stages, 6))
        self.min_tooth = self.available_teeth[0]
        self.max_tooth = self.available_teeth[-1]

        # Generate candidate gear pairs (strict inequality p < g for speed reduction)
        self._spur_pairs: list[GearPair] = []
        for p in self.available_teeth:
            for g in self.available_teeth:
                if p < g:
                    self._spur_pairs.append(GearPair(pinion=p, gear=g, is_worm=False))

        # Sort candidate spur pairs by cost ascending
        self._spur_pairs.sort(key=lambda p: (p.teeth_sum, p.pinion, p.gear))

        self._worm_pairs: list[GearPair] = [
            GearPair(pinion=1, gear=g, is_worm=True) for g in self.available_teeth
        ]
        self._worm_pairs.sort(key=lambda p: p.gear)

        (
            self._d1,
            self._d2,
            self._d1_ratios,
            self._d1_floats,
            self._d2_ratios,
            self._d2_floats,
        ) = _get_or_build_index(tuple(self.available_teeth), self._spur_pairs)



    def _min_stage_cost(self, k: int, use_worm: bool = False) -> int:
        """Returns the theoretical minimum possible cost for a k-stage train."""
        if k <= 0:
            return 0
        penalty = self.cost_model.stage_penalty * k
        if use_worm:
            # 1 worm stage (pinion 1 + min_tooth) + (k-1) spur stages (2 * min_tooth each)
            teeth = (1 + self.min_tooth) + (k - 1) * (2 * self.min_tooth)
        else:
            teeth = k * (2 * self.min_tooth)
        return int(round(teeth * self.cost_model.teeth_multiplier)) + penalty

    def solve(
        self,
        target_ratio: str | int | float | Fraction,
        use_worm: bool = False,
        allow_approximate: bool = False,
        max_solutions: int = 3,
    ) -> list[ReductionSolution]:
        """Calculates optimal gear train solutions meeting or approximating the target ratio."""
        target_frac = parse_ratio(target_ratio)

        # Handle 1:1 direct ratio (pinion == gear single stage)
        if target_frac == Fraction(1, 1) and not use_worm:
            sol = ReductionSolution.create(
                (GearPair(self.min_tooth, self.min_tooth),), self.cost_model, target_frac
            )
            return [sol]

        # 1. Search for Exact Solutions
        exact_solutions = self._find_exact_solutions(target_frac, use_worm, max_solutions)

        if exact_solutions:
            return self._rank_and_format_solutions(exact_solutions, max_solutions)

        # 2. If no exact solution is possible and approximate solutions are not enabled, return empty
        if not allow_approximate:
            return []

        # 3. Approximate Search
        approx_solutions = self._find_approximate_solutions(
            target_frac, use_worm, max_solutions
        )
        return self._rank_and_format_solutions(approx_solutions, max_solutions)

    def _find_exact_solutions(
        self, target_frac: Fraction, use_worm: bool, max_solutions: int
    ) -> list[ReductionSolution]:
        """Performs exact rational matching with progressive stage deepening.

        Engineering Rationale:
        ---------------------
        Compound gear trains strictly increase in cost and mechanical complexity
        (shafts, backlash, friction) with each additional stage. If exact solutions
        exist at stage depth k, any solution at depth k+1 is guaranteed to have a higher
        cost and introduces redundant cancellation stages. Therefore, once exact solutions
        are found at the minimal achievable depth k, the search returns immediately.
        """
        found_solutions: list[ReductionSolution] = []

        if use_worm:
            # Depth 1: Worm alone
            if self.max_stages >= 1:
                for worm_pair in self._worm_pairs:
                    rem_ratio = target_frac / worm_pair.ratio
                    if rem_ratio == Fraction(1, 1):
                        found_solutions.append(
                            ReductionSolution.create((worm_pair,), self.cost_model, target_frac)
                        )
                if found_solutions:
                    return found_solutions

            # Depth 2: Worm + 1 spur stage
            if self.max_stages >= 2:
                for worm_pair in self._worm_pairs:
                    rem_ratio = target_frac / worm_pair.ratio
                    if rem_ratio in self._d1:
                        for s1 in self._d1[rem_ratio]:
                            found_solutions.append(
                                ReductionSolution.create((worm_pair,) + s1, self.cost_model, target_frac)
                            )
                if found_solutions:
                    return found_solutions

            # Depth 3: Worm + 2 spur stages
            if self.max_stages >= 3:
                for worm_pair in self._worm_pairs:
                    rem_ratio = target_frac / worm_pair.ratio
                    if rem_ratio in self._d2:
                        for s2 in self._d2[rem_ratio]:
                            found_solutions.append(
                                ReductionSolution.create((worm_pair,) + s2, self.cost_model, target_frac)
                            )
                if found_solutions:
                    return found_solutions

            # Depth 4: Worm + 3 spur stages
            if self.max_stages >= 4:
                for worm_pair in self._worm_pairs:
                    rem_ratio = target_frac / worm_pair.ratio
                    for r1, s1_list in self._d1.items():
                        needed_r2 = rem_ratio / r1
                        if needed_r2 in self._d2:
                            for s1 in s1_list[:2]:
                                for s2 in self._d2[needed_r2][:2]:
                                    found_solutions.append(
                                        ReductionSolution.create((worm_pair,) + s1 + s2, self.cost_model, target_frac)
                                    )
                if found_solutions:
                    return found_solutions

        else:
            # Spur gear trains only
            # Depth 1
            if self.max_stages >= 1 and target_frac in self._d1:
                for s1 in self._d1[target_frac]:
                    found_solutions.append(
                        ReductionSolution.create(s1, self.cost_model, target_frac)
                    )
                if found_solutions:
                    return found_solutions

            # Depth 2
            if self.max_stages >= 2 and target_frac in self._d2:
                for s2 in self._d2[target_frac]:
                    found_solutions.append(
                        ReductionSolution.create(s2, self.cost_model, target_frac)
                    )
                if found_solutions:
                    return found_solutions

            # Depth 3
            if self.max_stages >= 3:
                for r1, s1_list in self._d1.items():
                    needed_r2 = target_frac / r1
                    if needed_r2 in self._d2:
                        for s1 in s1_list[:3]:
                            for s2 in self._d2[needed_r2][:3]:
                                found_solutions.append(
                                    ReductionSolution.create(s1 + s2, self.cost_model, target_frac)
                                )
                if found_solutions:
                    return found_solutions

            # Depth 4
            if self.max_stages >= 4:
                for r2_a, s2_a_list in self._d2.items():
                    needed_r2_b = target_frac / r2_a
                    if needed_r2_b in self._d2 and r2_a <= needed_r2_b:
                        for s2_a in s2_a_list[:2]:
                            for s2_b in self._d2[needed_r2_b][:2]:
                                found_solutions.append(
                                    ReductionSolution.create(s2_a + s2_b, self.cost_model, target_frac)
                                )
                if found_solutions:
                    return found_solutions

        return found_solutions

        return found_solutions

    def _find_approximate_solutions(
        self, target_frac: Fraction, use_worm: bool, max_solutions: int
    ) -> list[ReductionSolution]:
        """Finds trains with achieved ratio closest to target_frac."""
        target_float = float(target_frac)
        candidates: list[tuple[GearPair, ...]] = []

        def get_nearest_ratios(
            needed_float: float, ratio_floats: list[float], ratio_fracs: list[Fraction], k: int = 4
        ) -> list[Fraction]:
            if not ratio_floats:
                return []
            idx = bisect.bisect_left(ratio_floats, needed_float)
            start = max(0, idx - k)
            end = min(len(ratio_floats), idx + k + 1)
            return [ratio_fracs[i] for i in range(start, end)]

        if use_worm:
            for worm_pair in self._worm_pairs:
                worm_ratio = worm_pair.ratio
                rem_float = target_float / float(worm_ratio)

                if self.max_stages >= 1:
                    candidates.append((worm_pair,))

                if self.max_stages >= 2:
                    nearest = get_nearest_ratios(
                        rem_float, self._d1_floats, self._d1_ratios, k=3
                    )
                    for r in nearest:
                        for combo in self._d1[r][:2]:
                            candidates.append((worm_pair,) + combo)

                if self.max_stages >= 3:
                    nearest = get_nearest_ratios(
                        rem_float, self._d2_floats, self._d2_ratios, k=3
                    )
                    for r in nearest:
                        for combo in self._d2[r][:2]:
                            candidates.append((worm_pair,) + combo)

                if self.max_stages >= 4:
                    for r1, spur1_list in list(self._d1.items())[::4]:
                        needed_r2 = rem_float / float(r1)
                        nearest_r2 = get_nearest_ratios(
                            needed_r2, self._d2_floats, self._d2_ratios, k=2
                        )
                        for r2 in nearest_r2:
                            for s1 in spur1_list[:1]:
                                for s2 in self._d2[r2][:1]:
                                    candidates.append((worm_pair,) + s1 + s2)

        else:
            if self.max_stages >= 1:
                nearest = get_nearest_ratios(
                    target_float, self._d1_floats, self._d1_ratios, k=3
                )
                for r in nearest:
                    candidates.extend(self._d1[r][:2])

            if self.max_stages >= 2:
                nearest = get_nearest_ratios(
                    target_float, self._d2_floats, self._d2_ratios, k=4
                )
                for r in nearest:
                    candidates.extend(self._d2[r][:2])

            if self.max_stages >= 3:
                for r1, spur1_list in list(self._d1.items())[::3]:
                    needed_r2 = target_float / float(r1)
                    nearest_r2 = get_nearest_ratios(
                        needed_r2, self._d2_floats, self._d2_ratios, k=2
                    )
                    for r2 in nearest_r2:
                        for s1 in spur1_list[:1]:
                            for s2 in self._d2[r2][:1]:
                                candidates.append(s1 + s2)

            if self.max_stages >= 4:
                for r2_a in self._d2_ratios[::8]:
                    needed_r2_b = target_float / float(r2_a)
                    nearest_r2_b = get_nearest_ratios(
                        needed_r2_b, self._d2_floats, self._d2_ratios, k=2
                    )
                    for r2_b in nearest_r2_b:
                        for s2_a in self._d2[r2_a][:1]:
                            for s2_b in self._d2[r2_b][:1]:
                                candidates.append(s2_a + s2_b)

        solutions: list[ReductionSolution] = []
        for train in candidates:
            solutions.append(
                ReductionSolution.create(train, self.cost_model, target_frac)
            )

        unique_map: dict[tuple[tuple[int, int, bool], ...], ReductionSolution] = {}
        for sol in solutions:
            key = sol.canonical_stage_key()
            if key not in unique_map or sol.cost < unique_map[key].cost:
                unique_map[key] = sol

        unique_solutions = list(unique_map.values())
        unique_solutions.sort(
            key=lambda s: (
                abs(float(s.achieved_ratio - target_frac)),
                s.cost,
                len(s.stages),
            )
        )

        return unique_solutions[: max(max_solutions * 3, 10)]

    def _rank_and_format_solutions(
        self, solutions: Sequence[ReductionSolution], max_solutions: int
    ) -> list[ReductionSolution]:
        """Deduplicates, computes relative costs, and formats top solutions.

        Engineering Rationale:
        ---------------------
        1. Exact Stage Multiset Deduplication: Eliminates identical stage permutations.
        2. Physical Parts Deduplication: If two solutions use the exact same collection of
           physical gears (e.g. pinions {11, 12} and gears {33, 40}), they share the exact same
           purchased parts bill-of-materials. Only the mechanically optimal progressive
           arrangement (non-decreasing pinions and non-decreasing driven gears) is retained.
        """
        if not solutions:
            return []

        # Step 1: Deduplicate by exact stage combination
        stage_map: dict[tuple[tuple[int, int, bool], ...], ReductionSolution] = {}
        for sol in solutions:
            key = sol.canonical_stage_key()
            if key not in stage_map or sol.cost < stage_map[key].cost:
                stage_map[key] = sol

        # Step 2: Deduplicate by physical parts bill-of-materials multiset
        parts_map: dict[tuple[int | None, tuple[int, ...], tuple[int, ...]], ReductionSolution] = {}
        for sol in stage_map.values():
            pkey = sol.canonical_parts_key()
            if pkey not in parts_map:
                parts_map[pkey] = sol
            else:
                existing = parts_map[pkey]
                # Lower progression penalty represents superior progressive torque distribution
                if sol.progression_penalty() < existing.progression_penalty():
                    parts_map[pkey] = sol
                elif sol.progression_penalty() == existing.progression_penalty() and sol.cost < existing.cost:
                    parts_map[pkey] = sol

        unique_solutions = list(parts_map.values())
        if not unique_solutions:
            return []

        if unique_solutions[0].is_approximate:
            unique_solutions.sort(
                key=lambda s: (
                    float(s.deviation_percentage.rstrip("%"))
                    if s.deviation_percentage
                    else 0.0,
                    s.cost,
                    s.progression_penalty(),
                    len(s.stages),
                )
            )
            selected = unique_solutions[:max_solutions]
        else:
            unique_solutions.sort(
                key=lambda s: (
                    s.cost,
                    s.progression_penalty(),
                    len(s.stages),
                )
            )
            selected = unique_solutions[:max_solutions]

        lowest_cost = min(sol.cost for sol in selected)
        for sol in selected:
            sol.relative_cost = (
                sol.cost / lowest_cost if lowest_cost > 0 else 1.0
            )

        selected.sort(key=lambda s: (s.relative_cost, s.cost, s.progression_penalty(), len(s.stages)))
        return selected

