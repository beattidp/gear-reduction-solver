# Walkthrough: Epicyclic / Planetary Gear Reduction Solver

We have completed the implementation and verification of the **Epicyclic / Planetary Gear Configuration Solver** as an alternative solver in the Gear Reduction Solver application.

---

## What Was Implemented

### 1. Planetary Domain Models & Kinematics
- **`PlanetaryStator` Enum**: `RING`, `CARRIER`, and `SUN`.
- **`PlanetaryStage`**:
  - Implements the fundamental Willis equation:
    - **Ring Fixed**: Input = Sun, Output = Carrier $\rightarrow$ High-ratio speed reduction ($\text{Ratio} = 1 + R/S > 2.0$, same direction).
    - **Carrier Fixed**: Input = Sun, Output = Ring $\rightarrow$ Moderate-ratio reduction with inverted rotation ($\text{Ratio} = R/S > 1.0$, reverse direction).
    - **Sun Fixed**: Input = Ring, Output = Carrier $\rightarrow$ Low-ratio reduction ($1.0 < \text{Ratio} = 1 + S/R < 2.0$, same direction).
  - Validates physical and manufacturing constraints:
    - Coaxiality: $R = S + 2P$
    - Symmetrical meshing / assembly: $(S + R) \pmod N == 0$
    - Adjacent planet tip clearance: $(S + P) \sin(\pi/N) > P + 2$
- **`PlanetaryCostModel`**:
  - Accounts for 1 sun gear, $N$ identical planet gears, internal ring gear with multiplier ($1.5\times$), and carrier/bearing stage penalty ($60$).
- **`PlanetarySolution`**:
  - Encapsulates single-stage and cascaded multi-stage planetary trains, with JSON serialization and torque progression metrics.

### 2. Multi-Stage Planetary Solver Algorithm
- **`PlanetarySolver`**:
  - Pre-enumerates physically realizable single stages.
  - Searches 1 to $k$ stages via Meet-in-the-Middle and branch-and-bound graph traversal.
  - Minimal stage depth termination: terminates immediately once minimal stage exact solutions are found.
  - Supports `--stator {ring, carrier, sun, any}` filtering.
  - Supports bounded approximate search when exact ratios are unreachable.

### 3. CLI & Configuration Integration
- Extended `gear-reduction-solver` CLI:
  - `-p`, `--planetary`: Run planetary gear solver.
  - `--type {spur, planetary, all}`: Run spur, planetary, or both side-by-side.
  - `--stator {ring, carrier, sun, any}`: Filter by fixed member.
  - `--planets`: Planet count (default 3).
  - `--ring-multiplier`: Ring tooth cost weight (default 1.5).
  - `--max-ring-teeth`: Max allowable teeth on ring gear (default 120).
  - `--strict-ring-inventory`: Require ring gear teeth to be in `available_teeth`.

---

## Verification Results

### Automated Tests
48 unit tests passing across all suites:
```bash
PYTHONPATH=src pytest -v tests/
```
- `tests/test_planetary.py`: 15 passed (geometry, kinematics, multi-stage, approximations, CLI).
- `tests/test_cli.py`: 5 passed.
- `tests/test_models.py`: 14 passed.
- `tests/test_solver_exact.py`: 12 passed.
- `tests/test_solver_approx.py`: 2 passed.

### CLI Sample Outputs

#### Planetary Reduction for 4:1
```
$ python3 -m gear_reduction.cli -r 4:1 --planetary

=== Planetary Gear Reduction Solutions for Target Ratio 4:1 ===
#   | Configuration [Stator: S / P / R]              | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
----------------------------------------------------------------------------------------------------
1   | [Ring Fixed: S=12T P=12Tx3 R=36T]              | 4/1 (4.0000)     | 0.00%    | 162    | 1.0000
2   | [Ring Fixed: S=15T P=15Tx3 R=45T]              | 4/1 (4.0000)     | 0.00%    | 188    | 1.1605
3   | [Carrier Fixed: S=12T P=18Tx3 R=48T (Rev)]     | 4/1 (4.0000)     | 0.00%    | 198    | 1.2222
----------------------------------------------------------------------------------------------------
Found 3 planetary solution(s). Sorted from lowest to highest relative cost.
```

#### Side-by-Side Comparison for 10:1 (`--type all`)
```
$ python3 -m gear_reduction.cli -r 10:1 --type all

=== Spur / Worm Gear Reduction Solutions for Target Ratio 10:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [11T -> 33T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 196    | 1.0000
2   | [12T -> 36T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 200    | 1.0204
3   | [12T -> 39T] [13T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 204    | 1.0408
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.

=== Planetary Gear Reduction Solutions for Target Ratio 10:1 ===
#   | Configuration [Stator: S / P / R]              | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
----------------------------------------------------------------------------------------------------
1   | [Carrier Fixed: S=12T P=12Tx3 R=36T (Rev)] [Ring Fixed: S=18T P=12Tx3 R=42T] | 10/1 (10.0000)   | 0.00%    | 339    | 1.0000
2   | [Carrier Fixed: S=12T P=15Tx3 R=42T (Rev)] [Carrier Fixed: S=14T P=13Tx3 R=40T (Rev)] | 10/1 (10.0000)   | 0.00%    | 353    | 1.0413
3   | [Ring Fixed: S=18T P=12Tx3 R=42T] [Ring Fixed: S=22T P=11Tx3 R=44T] | 10/1 (10.0000)   | 0.00%    | 358    | 1.0560
----------------------------------------------------------------------------------------------------
Found 3 planetary solution(s). Sorted from lowest to highest relative cost.
```
