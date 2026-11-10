# Walkthrough: Phase 1 — Core Domain Solver & CLI

We have implemented and verified **Phase 1: Core Domain Solver and CLI** for the Gear Reduction Solver application.

---

## Changes Made

### 1. Core Domain Models (`src/gear_reduction/core/models.py`)
- **`GearPair`**: Models single spur and worm stages. Enforces $P \le G$ (and $P = 1$ for single-start worm stages). Computes exact rational ratio $G / P$ and tooth sum $P + G$.
- **`CostModel`**: Calculates absolute cost: $\sum (P_i + G_i) + 50 \times \text{stages}$.
- **`ReductionSolution`**: Canonical stage sorting (worm stage locked at index 0, spur stages sorted ascending by pinion teeth), relative cost weights ($\text{current} / \text{lowest}$ with lowest $= 1.0$), and `deviationPercentage` formatted string (e.g. `"0.52%"`).

### 2. High-Performance Combinatorial Solver (`src/gear_reduction/core/solver.py`)
- **Meet-in-the-Middle Indexing**: Pre-indexes single-stage and 2-stage combinations with exact rational ratios and cost-sorted stage limits. Cached globally across solver instances.
- **Branch-and-Bound Depth Pruning**: Avoids searching deeper stages when shallower stages already found optimal low-cost exact solutions.
- **Exact & Approximate Solving**: Handles exact rational fraction matching; when approximate mode is enabled, queries nearest ratios with binary search, sorts by lowest error, computes relative costs, and formats results.

### 3. Configuration & CLI Interface
- **`config/default_config.json`** & **`src/gear_reduction/config.py`**: Configurable presets for gear tooth limits (11T–40T), cost penalties, and solver defaults.
- **`src/gear_reduction/cli.py`**: Command-line interface with formatted ASCII tables and structured `--json` output.

---

## Verification Results

### Automated Test Suite (`pytest`)
Ran 29 unit tests covering models, costing, sorting rules, exact ratios, worm drives, approximate deviations, and CLI options:
```bash
PYTHONPATH=src pytest -v tests/
============================== 29 passed in 7.17s ==============================
```

### CLI Execution Examples

#### 1. Exact Reduction Ratio (`10:1`)
```bash
$ python3 -m gear_reduction.cli -r 10:1

=== Gear Reduction Solutions for Target Ratio 10:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [11T -> 33T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 196    | 1.0000
2   | [11T -> 40T] [12T -> 33T]              | 10/1 (10.0000)   | 0.00%    | 196    | 1.0000
3   | [12T -> 36T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 200    | 1.0204
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.
```

#### 2. Worm Drive Input Stage (`60:1`)
```bash
$ python3 -m gear_reduction.cli -r 60:1 --worm

=== Gear Reduction Solutions for Target Ratio 60:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [Worm(1T) -> 22T] [11T -> 30T]         | 60/1 (60.0000)   | 0.00%    | 164    | 1.0000
2   | [Worm(1T) -> 30T] [11T -> 22T]         | 60/1 (60.0000)   | 0.00%    | 164    | 1.0000
3   | [Worm(1T) -> 20T] [11T -> 33T]         | 60/1 (60.0000)   | 0.00%    | 165    | 1.0061
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.
```

#### 3. Unattainable Ratio Without Approx vs. With Approx (`71:1`)
Without approx:
```bash
$ python3 -m gear_reduction.cli -r 71:1
No gear reduction solutions found for target ratio 71:1.
```
With approx enabled (`--approx`):
```bash
$ python3 -m gear_reduction.cli -r 71:1 --approx

=== Gear Reduction Solutions for Target Ratio 71:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [11T -> 25T] [11T -> 33T] [11T -> 35T] [11T -> 36T] | 94500/1331 (70.9992) | 0.00%    | 373    | 1.0000
2   | [11T -> 27T] [11T -> 30T] [11T -> 35T] [12T -> 40T] | 94500/1331 (70.9992) | 0.00%    | 377    | 1.0107
3   | [11T -> 32T] [11T -> 32T] [11T -> 34T] [14T -> 38T] | 661504/9317 (70.9997) | 0.00%    | 383    | 1.0268
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.
```

#### 4. Structured JSON Output (`--json`)
```bash
$ python3 -m gear_reduction.cli -r 10:1 --json
{
  "target_ratio": "10/1",
  "target_ratio_float": 10.0,
  "use_worm": false,
  "allow_approximate": false,
  "solutions_count": 3,
  "solutions": [
    {
      "stages": [
        {"pinion": 11, "gear": 33},
        {"pinion": 12, "gear": 40}
      ],
      "achieved_ratio_fraction": "10/1",
      "achieved_ratio": 10.0,
      "cost": 196,
      "relative_cost": 1.0,
      "is_approximate": false
    },
    ...
  ]
}
```
