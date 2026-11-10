# Feature Documentation: Phase 1 — Core Domain Solver & CLI

**Module**: `gear_reduction`  
**Status**: Implemented & Verified  
**Date**: 2026-11-10  
**Authors**: Antigravity & beattidp  

---

## 1. Overview & Architecture

Phase 1 implements the complete mathematical core domain solver and command-line interface (CLI) for multi-stage compound gear train design according to specifications in [`.proposal`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/.proposal).

### Component Layout
```
src/gear_reduction/
├── __init__.py           # Package exports and version metadata
├── config.py             # SolverConfig loader for JSON configuration
├── cli.py                # Command-line interface with table and JSON formatting
└── core/
    ├── __init__.py       # Core package exports
    ├── models.py         # GearPair, ReductionSolution, CostModel
    └── solver.py         # ReductionSolver with Meet-in-the-Middle indexing
```

---

## 2. Core Domain Models (`gear_reduction.core.models`)

### `GearPair`
Represents an individual reduction stage:
* `pinion: int`: Tooth count of driving gear (1 for a single-start worm drive).
* `gear: int`: Tooth count of driven gear.
* `is_worm: bool`: True if driving member is a worm screw.
* Invariant enforcement: $P \le G$ for spur stages, $P = 1$ for worm stages.
* `ratio: Fraction`: Exact rational reduction ratio $G / P$.
* `teeth_sum: int`: $P + G$.

### `CostModel`
Fabrication & assembly penalty formula:
$$\text{Cost} = \sum_{i=1}^k (P_i + G_i) + (\text{stage\_penalty} \times k)$$
* Default `stage_penalty` $= 50$.

### `ReductionSolution`
Represents a multi-stage gear train:
* `stages: tuple[GearPair, ...]`: Enforces canonical sorting:
  1. Worm drive stage (if present) is locked at index 0.
  2. Spur stages are sorted in ascending order by pinion tooth count (breaking ties by gear tooth count).
* `achieved_ratio: Fraction`: Exact cascade product $\prod \text{stage.ratio}$.
* `cost: int`: Absolute cost from `CostModel`.
* `relative_cost: float`: Normalized to lowest cost solution in the candidate set:
  $$\text{relative\_cost} = \frac{\text{current\_cost}}{\min(\text{candidate\_costs})} \quad (\text{cheapest} = 1.0)$$
* `is_approximate: bool`: True when achieved ratio deviates from target ratio.
* `deviation_percentage: str`: Formatted string `X.XX%`:
  $$\text{deviationPercentage} = \left|\frac{\text{achievedRatio} - \text{targetRatio}}{\text{targetRatio}}\right| \times 100\%$$
* `canonical_stage_key()`: Hashable stage signature to deduplicate stage permutations (since stage order is commutative).

---

## 3. Solver Algorithm (`gear_reduction.core.solver`)

### High-Performance Combinatorial Search
1. **Meet-in-the-Middle Indexing**:
   * Pre-indexes 1-stage ($D_1$) and 2-stage ($D_2$) spur ratios into exact `Fraction` lookup tables with cost-sorted candidate stages.
   * Cached globally per available tooth set (`_INDEX_CACHE`) for instant reuse.
2. **Branch-and-Bound Depth Pruning**:
   * Progressive deepening over stages $k \in [1, 4]$.
   * Theoretical minimum cost at depth $k$: $\text{min\_cost}(k) = k \times (2 \times \min(T) + 50)$.
   * If shallower stages have already found `max_solutions` exact solutions whose costs are lower than $\text{min\_cost}(k)$, deeper searches are pruned immediately.
3. **Exact Solver**:
   * Worm stage (if enabled) is evaluated at stage 1, querying $D_1$ and $D_2$ for the remainder $R / G_{\text{worm}}$.
   * Spur trains query $D_1$ ($k=1$), $D_2$ ($k=2$), $D_1 \times D_2$ ($k=3$), and $D_2 \times D_2$ ($k=4$) in $O(1)$ dictionary lookups.
4. **Approximate Solver**:
   * Triggered only if `allow_approximate=True` and no exact solution exists.
   * Performs nearest-neighbor binary search (`bisect`) on sorted ratio floats.
   * Sorts solutions by minimum error, calculates relative costs, and outputs ascending by relative cost.

---

## 4. Command-Line Interface (`gear_reduction.cli`)

### CLI Syntax
```bash
python3 -m gear_reduction.cli -r <ratio> [options]
```

### Options:
* `-r, --ratio`: Target reduction ratio (e.g., `10:1`, `25:2`, `12.5`).
* `-w, --worm`: Use single-start worm for the input stage.
* `-a, --approx`: Allow approximate solutions if no exact match exists.
* `-n, --max-solutions`: Maximum solutions to find (default: 3).
* `-s, --max-stages`: Maximum stages to search (default: 4).
* `-t, --teeth`: Custom tooth inventory (e.g., `11-40` or `12,16,24,30,40`).
* `-c, --config`: Path to custom JSON configuration file.
* `--json`: Emit structured JSON output.

### Output Example (Terminal Table):
```
=== Gear Reduction Solutions for Target Ratio 60:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [Worm(1T) -> 22T] [11T -> 30T]         | 60/1 (60.0000)   | 0.00%    | 164    | 1.0000
2   | [Worm(1T) -> 30T] [11T -> 22T]         | 60/1 (60.0000)   | 0.00%    | 164    | 1.0000
3   | [Worm(1T) -> 20T] [11T -> 33T]         | 60/1 (60.0000)   | 0.00%    | 165    | 1.0061
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.
```

---

## 5. Automated Verification

29 unit tests covering all models, costing, sorting rules, exact ratios, worm drives, approximate deviations, and CLI options:
```bash
PYTHONPATH=src pytest -v tests/
============================== 29 passed in 7.17s ==============================
```
