# Implementation Plan: Phase 1 — Core Domain Solver & CLI

Implement the Core Domain Solver and Command-Line Interface (CLI) for the Gear Reduction Solver application according to the specifications in [`.proposal`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/.proposal).

## User Review Required

> [!IMPORTANT]
> - **Input Ratio Format**: The CLI will support ratios specified as `in:out` (e.g. `10:1`, `25:2`, `7.5:1`), as a single float/int reduction factor (e.g. `10.0`), or as separate numerator/denominator flags.
> - **Max Stages Limit**: Multi-stage gear trains will search depths up to 4 stages by default (configurable up to 6). In practice, 4 stages cover reductions up to $(40/11)^4 \approx 174:1$ for spur gears (and up to $174 \times 40 \approx 6980:1$ with a worm drive stage).
> - **Zero-dependency Core**: The domain core will use Python standard library modules (`fractions`, `dataclasses`, `itertools`, `math`, `json`, `argparse`). `pytest` will be used for testing.

## Proposed Changes

### Core Domain Model & Costing (`src/gear_reduction/core/`)

#### [NEW] [`src/gear_reduction/core/models.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/models.py)
- `GearPair`:
  - `pinion: int`, `gear: int`, `is_worm: bool = False`.
  - Validation: Pinion $\le$ Gear (unless worm, where pinion is 1 and gear $\in$ available teeth).
  - Reduction ratio: $\text{ratio} = \frac{\text{gear}}{\text{pinion}}$ using `fractions.Fraction`.
  - Tooth sum: $P + G$.
- `GearTrain` / `ReductionSolution`:
  - Sequence of `GearPair` objects.
  - Total achieved ratio: $\prod \text{stage\_ratio}$.
  - Absolute cost: $\sum (P_i + G_i) + 50 \times k$.
  - Relative cost: $C / C_{\min}$ (computed after ranking candidate set).
  - Canonical sorting: Spur stages sorted ascending by pinion tooth count (breaking ties by gear tooth count); worm stage locked at index 0.
  - `deviation_percentage`: formatted string `"X.XX%"` for approximate solutions.
- `CostModel`:
  - Configurable parameters: `stage_penalty: int = 50`, `tooth_weight: float = 1.0`.

#### [NEW] [`src/gear_reduction/core/solver.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py)
- `ReductionSolver`:
  - Input configuration: `available_teeth: list[int]`, `target_ratio: Fraction`, `use_worm: bool`, `allow_approximate: bool`, `max_solutions: int = 3`, `max_stages: int = 4`.
  - **Symmetry-broken Stage Generation**: Generates candidate spur pairs and searches combinations with replacement to eliminate order permutations.
  - **Exact Solver**:
    - Progressive deepening over stage counts $k \in [1, \text{max\_stages}]$.
    - Prunes branches exceeding the best known exact cost.
  - **Approximate Solver**:
    - When no exact solution exists and `allow_approximate=True`:
    - Evaluates trains minimizing $|R_{\text{achieved}} - R_{\text{target}}|$, breaking ties with lowest cost.
  - **Ranking & Formatting**:
    - Deduplicates identical gear stage sets.
    - Computes relative cost weights (best solution = 1.0).
    - Sorts by relative cost ascending and limits to `max_solutions`.

---

### Configuration & CLI (`src/gear_reduction/`)

#### [NEW] [`src/gear_reduction/config.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/config.py)
- Configuration loader for JSON presets (defaulting to 11T–40T, stage penalty 50, max solutions 3).

#### [NEW] [`config/default_config.json`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/config/default_config.json)
- Default configuration file.

#### [NEW] [`src/gear_reduction/cli.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/cli.py)
- Command-line interface:
  - `--ratio` / `-r`: Target reduction ratio (e.g. `10:1` or `12.5`).
  - `--worm` / `-w`: Enable worm drive for first stage.
  - `--approx` / `-a`: Allow approximate solutions if no exact solution exists.
  - `--max-solutions` / `-n`: Default 3.
  - `--teeth` / `-t`: Custom teeth list (defaults to 11–40).
  - `--json`: Output solutions in JSON format (ready for programmatic integration).
  - Formatted table display in terminal.

---

### Test Suite (`tests/`)

#### [NEW] [`tests/test_models.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/tests/test_models.py)
- Test `GearPair` ratio calculation, worm stage formatting `{pinion: 1, gear: N}`, and pinion $\le$ gear constraint.
- Test `CostModel` with single and multi-stage trains (teeth sum + 50 * stages).
- Test canonical sorting (ascending by pinion, worm always first).

#### [NEW] [`tests/test_solver_exact.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/tests/test_solver_exact.py)
- Verify exact solutions for known reachable ratios (e.g., $2:1$, $10:1$, $25:2$).
- Verify that without `--approx`, unattainable ratios return zero solutions.
- Verify worm drive solution generation (stage 1 has pinion = 1).
- Verify solution uniqueness (no duplicate stage sets in different orders).
- Verify relative cost weighting (lowest cost = 1.00).

#### [NEW] [`tests/test_solver_approx.py`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/tests/test_solver_approx.py)
- Verify approximate solutions for prime/unattainable ratios (e.g. $71:1$).
- Verify correct calculation and string formatting of `deviationPercentage` (e.g. `"0.52%"`).
- Verify closest ratio solutions are prioritized.

---

## Verification Plan

### Automated Tests
Run pytest in the project's pyenv environment:
```bash
pytest -v tests/
```

### Manual Verification
1. Run CLI for an exact ratio:
   ```bash
   python -m gear_reduction.cli -r 10:1
   ```
2. Run CLI with worm drive:
   ```bash
   python -m gear_reduction.cli -r 60:1 --worm
   ```
3. Run CLI with an unattainable ratio (expecting no solution):
   ```bash
   python -m gear_reduction.cli -r 71:1
   ```
4. Run CLI with an unattainable ratio with approximate flag enabled:
   ```bash
   python -m gear_reduction.cli -r 71:1 --approx
   ```
5. Run CLI with JSON output:
   ```bash
   python -m gear_reduction.cli -r 10:1 --json
   ```
