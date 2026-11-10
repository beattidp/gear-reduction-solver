# Feature Documentation: Machine-Readable JSON & Formal Schema

## Overview
The Gear Reduction Solver provides machine-readable JSON exports across both the Command-Line Interface (`--json`) and the Web Interface ("Copy JSON"). All JSON outputs are formally specified by a JSON Schema conforming to **JSON Schema Draft 2020-12**.

---

## Schema Location & Hosting

- **Repository File**: [`schema/gear_reduction_solution.schema.json`](../../schema/gear_reduction_solution.schema.json)
- **Live GitHub Pages URL**: `https://beattidp.github.io/gear-reduction-solver/schema/gear_reduction_solution.schema.json`

---

## Schema Structure & Models

The schema defines four primary components:

### 1. `SpurStage` & `PlanetaryStage`
- **SpurStage**:
  - `pinion`: Driving pinion tooth count (integer $\ge 1$; 1 for a single-start worm).
  - `gear`: Driven gear tooth count (integer $\ge 1$).
- **PlanetaryStage**:
  - `sun`: Sun gear tooth count (integer $\ge 1$).
  - `planet`: Planet gear tooth count (integer $\ge 1$).
  - `ring`: Internal ring gear tooth count (integer $\ge 1$, $R = S + 2P$).
  - `planets_count`: Number of planets on carrier (integer $\ge 2$, default 3).
  - `stator`: Enum (`"ring"`, `"carrier"`, `"sun"`).
  - `input`: Enum (`"sun"`, `"ring"`).
  - `output`: Enum (`"carrier"`, `"ring"`).
  - `ratio`: String fraction (e.g. `"4/1"`).
  - `is_inverted`: Boolean (true for carrier-fixed).

### 2. `SpurSolution` & `PlanetarySolution`
- `stages`: Array of `SpurStage` or `PlanetaryStage`.
- `achieved_ratio_fraction`: Exact rational fraction string (e.g. `"10/1"`).
- `achieved_ratio`: Floating-point numeric ratio (e.g. `10.0`).
- `cost`: Absolute integer fabrication cost.
- `relative_cost`: Floating-point relative cost normalized to the lowest-cost solution (lowest = `1.0000`).
- `is_approximate`: Boolean flag.
- `deviation_percentage`: Formatted string (e.g. `"0.50%"`) or `null` if exact.
- `is_inverted` (Planetary): Boolean indicating if output rotation is reversed.

### 3. `CliOutputEnvelope`
Top-level wrapper emitted by CLI with `--json`:
- `target_ratio`: Requested target ratio fraction string.
- `target_ratio_float`: Numeric target ratio.
- `mode`: Enum (`"spur"`, `"planetary"`, `"all"`).
- `solutions_count`: Number of solutions returned.
- `solutions`: Array of solution objects.
- `spur_solutions`: Optional array (populated in `"all"` mode).
- `planetary_solutions`: Optional array (populated in `"planetary"` or `"all"` mode).

---

## Automated Validation
Automated validation is verified via the `jsonschema` library in `tests/test_schema.py`:
```bash
PYTHONPATH="src:." pytest -v tests/test_schema.py
```
Validates:
1. Schema syntax conforms to Draft 2020-12 via `jsonschema.validators.validator_for()`.
2. CLI `--json` outputs in `spur`, `planetary`, and `all` modes validate strictly against the schema.
3. Web-exported solution arrays validate strictly against the schema.
