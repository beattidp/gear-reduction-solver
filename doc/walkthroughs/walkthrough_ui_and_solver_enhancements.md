# Walkthrough: Stage Expansion, Ratio Inversion, and Configurable Gear Inventory

We have implemented and verified all requested enhancements across the core mathematical solvers, configuration system, command-line interface, and browser-based WebAssembly application.

---

## Key Changes Implemented

### 1. Ratio Inversion & Flexible Input Formats
- **Uniform Mechanical Reduction Interpretation**:
  - `parse_ratio()` in `solver.py` automatically detects when input ratio is strictly $< 1.0$ (e.g., `1:4`, `1/4`, `0.25`, `2:5`, `1:100`).
  - Automatically inverts the fraction ($1 / \text{ratio}$) so that `1:4` evaluates to `4.0:1` (meaning output rotates at 1/4 the input speed, a 4:1 mechanical speed reduction).
  - Handles string formats: `"1:4"`, `"1/4"`, `"0.25"`, `"4:1"`, `"4"`, `"13.5"`, `"127/50"`.
- **Live UI Feedback**:
  - Dynamic interpretation banner added beneath ratio inputs on both Spur and Planetary tabs.
  - Typing `1:4` immediately displays: *"Interpreted as speed reduction of 4:1 (ratio: 4.0000)"*.

---

### 2. Stage Limit Expansion & Prime Factor Reachability Guard
- **Spur Stages Expanded to 6**:
  - Extended exact search depth logic up to 6 stages with meet-in-the-middle index composition and early termination.
  - Depth 5 candidate sampling added to approximate search.
  - UI dropdown updated to allow up to **6 Stages**.
- **Planetary Stages Expanded to 4**:
  - High-performance Meet-in-the-Middle 2-stage combination index (`d2_map`) implemented in `_search_exact_depth()`.
  - Accelerates depth 3 and depth 4 searches from combinatorial explosion ($> 20\text{ s}$) down to $< 5\text{ ms}$.
  - UI dropdown updated to allow up to **4 Stages**.
- **Prime Factor Reachability Pruning**:
  - Implemented `get_prime_factors(n)` and `check_prime_reachability(target_frac, available_teeth, use_worm)`.
  - A compound gear train $R = \prod (g_i / p_i)$ can only form prime factors present in the prime factorizations of the tooth counts.
  - For prime ratios that cannot be formed by available teeth (e.g., $43:1$ with teeth $\le 40$), the solver detects this in $O(\log N)$ arithmetic operations and short-circuits immediately without wasting compute.

---

### 3. Configurable Gear Catalog & Custom Tooth Inventory
- **Separation of Known Catalog & Active Available Subset**:
  - `known_gear_teeth`: Full set of recognized physical gears (now includes **9T** and **10T** by default: 9–40).
  - `available_gear_teeth`: The active subset enabled for reduction calculations.
- **Arbitrary Custom Gear Sizes**:
  - Custom gear sizes can be added (e.g., **52T**) without requiring intermediate sizes (41T–51T).
  - Interactive "Gear Teeth Catalog & Inventory" modal in web UI allows:
    - Adding custom gear sizes with instant validation ($> 0$, no duplicates).
    - Removing custom gear sizes with a single click.
    - Exporting active gear configuration to `gear_reduction_config.json`.
    - Importing JSON configurations directly via file upload.
    - Resetting inventory to default 9–40T.
- **CLI Configuration Flags**:
  - `--config-show`: Dumps current configuration.
  - `--config-export PATH`: Exports configuration to JSON file.
  - `--teeth`: Accepts comma-separated discrete teeth and ranges (e.g., `9-40,52`).

---

## Verification Results

### Automated Test Suite
Ran full test suite including new tests in `tests/test_enhancements.py` and `tests/test_solver_exact.py`:
- **74 passing tests** across core solver, planetary solver, configuration, CLI, and enhancements.
- Prime reachability successfully short-circuits prime targets like `43/1` and `127/1` in `< 0.1 ms`.
- 5 and 6 stage spur trains compute exact multi-stage reductions in `< 15 ms`.
- 4 stage planetary trains compute exact high-reduction solutions in `< 5 ms`.
- Web distribution bundle `web/python/gear_reduction.zip` rebuilt and verified.
