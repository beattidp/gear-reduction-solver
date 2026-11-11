# Feature: UI and Solver Enhancements (Stage Scaling, Ratio Normalization, Configurable Gear Inventory)

## Overview
This feature introduces key kinematics, algorithmic, and user-experience enhancements to both the Python core engine and the client-side Pyodide WebAssembly interface:
1. **Bidirectional Speed Reduction Normalization**:
   - Understands input entered as a fraction (e.g. `1/4` or `0.25`) or low:high ratio (`1:4`).
   - Automatically inverts inputs strictly $< 1.0$ into equivalent speed reduction ratios ($R = 1 / \text{input}$, e.g. `1:4` &rarr; `4:1` or `Fraction(4, 1)`).
   - Provides instant live interpretation feedback in the Web UI.
2. **Mathematical Prime-Factor Reachability Filter**:
   - Analyzes target ratios in $O(\log N)$ time by decomposing reduced numerator and denominator into unique prime factors.
   - Proves whether an exact solution is mathematically possible given the active tooth inventory.
   - For impossible prime ratios (e.g. 43:1 with teeth up to 40T), immediately short-circuits exact search (0 ms) and provides informative diagnostics, directing the user to approximate mode without wasted CPU cycles.
3. **Stage Depth Expansion (Up to 6 Spur / 4 Planetary Stages)**:
   - Expands spur gear train solving up to 6 stages using meet-in-the-middle index composition and branch-and-bound pruning.
   - Expands planetary solving up to 4 cascaded stages using $O(M)$ meet-in-the-middle stage pair lookups.
4. **Configurable Known vs. Available Gear Catalog**:
   - Expands default recognized gears to include common **9T and 10T** pinions (defaulting to 9T–40T).
   - Separates **Known Gears** (full inventory catalog) from **Available Gears** (active calculation subset).
   - Enables defining arbitrary custom non-contiguous gear sizes (e.g. 52T without requiring 41T–51T).
   - Provides full JSON configuration export/import across CLI (`--config-export`, `--config-show`) and Web UI (download/upload JSON file, synced to `localStorage`).

---

## Architecture & API

### Core Solver Normalization (`src/gear_reduction/core/solver.py`)
- [`parse_ratio(ratio_input)`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py):
  Parses strings (`"10:1"`, `"1:4"`, `"25:2"`, `"1/4"`), floats (`0.25`, `12.5`), integers, or `Fraction`. Inverts any positive value $< 1.0$ to $1 / \text{ratio}$.
- [`check_prime_reachability(target_frac, available_teeth, use_worm)`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py):
  Extracts unique prime factors $\mathcal{P}_{\text{gears}}$ and checks if $\mathcal{P}_{\text{target}} \subseteq \mathcal{P}_{\text{gears}}$. Returns `(is_reachable, unreachable_prime)`.
- [`ReductionSolver._find_exact_solutions`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py):
  Supports stage depths 1 through 6 with branch-and-bound and early termination.

### Planetary Solver (`src/gear_reduction/core/planetary_solver.py`)
- [`PlanetarySolver.solve`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/planetary_solver.py):
  Supports `max_stages` up to 4 with Meet-in-the-Middle 2-stage indexing (`d2_map`), achieving $< 5\text{ ms}$ search times for 4 cascaded planetary stages.

### Configuration (`src/gear_reduction/config.py`)
- `SolverConfig`:
  - `known_gear_teeth`: `list[int]` (default: 9–40).
  - `available_gear_teeth`: `list[int]` (default: 9–40).
  - `add_known_gear(teeth: int, enable: bool = True)`.
  - `remove_known_gear(teeth: int)`.
  - `set_gear_availability(teeth: int, available: bool)`.
  - `to_dict() -> dict[str, Any]`, `save(path)`, `load(path)`.

### Web Client (`web/`)
- **Ratio Interpretation Hint**: Real-time feedback beneath ratio inputs explaining how inputs are normalized.
- **Inventory Modal Dialog**:
  - Add Custom Gear Size input field and validation.
  - Known gears grid with active/inactive toggles and custom gear removal.
  - Export and Import JSON buttons with client-side file reading and download generation.
  - Multi-session persistence in `localStorage` under `gear_reduction_config_v2`.

---

## Verification
- Automated tests in `tests/test_enhancements.py` and `tests/test_solver_exact.py`:
  - Ratio inversion tests (`1:4`, `1/4`, `0.25`, `2:5`, `4:1`, `1:1`).
  - Prime reachability check and solver fast exit for unreachable prime ratios.
  - Custom 52T gear addition and usage in solutions.
  - 5-stage and 6-stage spur trains and 4-stage planetary trains.
  - CLI `--config-show`, `--config-export`, and discrete teeth parsing.
- 74 automated tests passing in test suite.
