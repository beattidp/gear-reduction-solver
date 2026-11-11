# UI and Solver Enhancements: Stage Scaling, Ratio Normalization, and Configurable Gear Inventories

## Overview & Background
Through close inspection of the current UI and solver backend, several usability, mathematical, and configuration opportunities have been identified:
1. **Stage Scaling & Upper Bounds**: The UI and solver currently cap stages at 4 (Spur) and 3 (Planetary). Users need the ability to specify higher stage counts (up to 6 stages for spur, 4 for planetary) to achieve large reductions. However, searching high depths for prime or prime-factor ratios not present in the gear inventory can lead to prolonged computation without results. A mathematical prime-factor reachability check is needed to detect insolvability instantly.
2. **Reduction Ratio Interpretation**: In speed reduction contexts, ratios are frequently entered as `output:input` (e.g. `1:4` or `1/4` or `0.25`), representing the speed fraction. Currently, values $< 1$ either raise errors or return zero results. The system should interpret fractions or ratios $< 1$ as the inverse reduction ($1 / \text{ratio}$), so `1:4` is automatically resolved as a `4:1` (4x) reduction.
3. **Known vs. Available Gear Inventory**: Gear sizes need clear separation between:
   - **Known Gears (`known_gear_teeth`)**: The catalog of recognized physical gear sizes. This default should be expanded to include common **9T and 10T** gears (defaulting to 9T through 40T).
   - **Available Gears (`available_gear_teeth`)**: The active subset of known gears selected for a given and subsequent calculations (persisted across sessions).
   - **Custom Non-Contiguous Sizes**: The ability to define arbitrary additional sizes (e.g. 52T without needing 41T to 51T).
   - **JSON Configuration & Web Sync**: Means to import/export and persist JSON configuration in the backend and web interface.

---

## User Review Required

> [!IMPORTANT]
> **Stage Upper Limits & Efficiency Realism**:
> In physical compound gear design, exceeding 6 spur stages or 4 planetary stages is seldom practical due to compounding mechanical efficiency loss ($0.95^6 \approx 73\%$), backlash, and shaft alignment complexity. We propose capping Spur stages at **6** and Planetary stages at **4**, with prominent UI advisories when selecting $\ge 5$ stages.

> [!NOTE]
> **Prime Factor Reachability Filter**:
> For any exact reduction ratio $R = \prod (g_i / p_i)$, the numerator in lowest terms can only contain prime factors present in the prime factorizations of available gear teeth $\bigcup \text{prime\_factors}(g)$. If the target ratio contains an unreachable prime factor (e.g. 43, 47, 53 with gears $\le 40$), the solver mathematically proves exact insolvability in $O(\log N)$ time, avoiding futile multi-stage combinatorial loops and instantly guiding the user to approximate mode.

---

## Proposed Changes

Grouped by component layer:

### Core Solver & Domain Layer (`src/gear_reduction/core/`)

#### [MODIFY] [solver.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py)
- **Ratio Inversion Normalization**:
  Update [`parse_ratio()`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py#L47-L86) to automatically invert any ratio strictly less than 1.0 ($R < 1 \implies 1/R$). A target of `"1:4"`, `"1/4"`, or `0.25` will normalize to `Fraction(4, 1)`.
- **Prime Factor Reachability Validation**:
  Add `is_ratio_factorable(target_frac: Fraction, available_teeth: Sequence[int]) -> tuple[bool, int | None]` to check if all prime factors in `target_frac.numerator` are composable from available gear teeth. If unreachable prime $q$ is detected:
  - Exact solver returns `[]` immediately (0 ms) with logged diagnostic.
  - Approximate solver bypasses exact combinatorial searching and directly runs nearest-ratio searches.
- **Stage Depth Expansion (Up to 6 Stages)**:
  Implement depths 5 and 6 in [`ReductionSolver._find_exact_solutions`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/solver.py#L245-L358) and `_find_approximate_solutions` using meet-in-the-middle index composition ($d2 + d3$, $d3 + d3$, or $d2 + d2 + d1$) with candidate caps and branch-and-bound pruning to ensure calculation times remain $< 50\text{ ms}$.

#### [MODIFY] [planetary_solver.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/planetary_solver.py)
- Update [`PlanetarySolver.solve`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/planetary_solver.py#L92-L155) to support input ratios $< 1$ by applying `parse_ratio()` with ratio inversion ($1/R$).
- Support `max_stages` up to 4 for planetary stages.
- Add prime-factor reachability check for ring/sun combinations.

---

### Configuration & CLI Layer (`src/gear_reduction/`)

#### [MODIFY] [config.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/config.py)
- Update `SolverConfig` dataclass:
  - Add `known_gear_teeth: list[int]` defaulting to `[9, 10, 11, ..., 40]`.
  - Add `available_gear_teeth: list[int]` defaulting to `[9, 10, 11, ..., 40]`.
  - Maintain backward compatibility for `default_enabled_teeth`, `min_gear_teeth`, and `max_gear_teeth`.
  - Add methods `to_dict()`, `save(path)`, `add_known_gear(teeth: int)`, and `set_gear_availability(teeth: int, available: bool)`.
- Support non-contiguous custom teeth (e.g. including 52 without 41–51).

#### [MODIFY] [config/default_config.json](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/config/default_config.json)
- Expand default configuration with `known_gear_teeth` including **9 and 10**, and `available_gear_teeth`.
- Support custom gear sizes specification.

#### [MODIFY] [cli.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/cli.py)
- Update `--stages` argument help and validation to accept up to 6 stages.
- Update `--teeth` parsing to support explicit discrete lists (e.g. `9-40,52`).
- Add `--config-export` and `--config-import` options or `--show-config` to inspect and modify JSON configuration.

---

### WebAssembly & Client-Side UI (`web/`)

#### [MODIFY] [web/index.html](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/web/index.html)
- **Spur Max Stages Dropdown**: Expand options from `1..4` to `1..6 Stages` (with high-stage advice).
- **Planetary Max Stages Dropdown**: Expand options from `1..3` to `1..4 Stages`.
- **Target Ratio Live Feedback**: Add a helper caption below the ratio input:
  - Displays live interpretation (e.g. `"Interpreted as 4:1 (4.0x speed reduction)"` when `1:4` or `1/4` is typed).
- **Inventory Modal Redesign**:
  - Show "Known Gears" catalog with 9T–40T by default.
  - "Add Custom Gear Size": input field + button to add arbitrary sizes (e.g. 52T).
  - Ability to delete/remove added custom gears.
  - "Export JSON" and "Import JSON" buttons to download and load custom configuration JSON.
  - Active count badge and selection buttons ("Select All Known", "Deselect All", "Reset to Default (9–40T)").

#### [MODIFY] [web/js/app.js](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/web/js/app.js)
- Update state management:
  - `knownTeeth: Set<number>` (default: 9..40 + custom).
  - `availableTeeth: Set<number>` (default: all known teeth).
- Add live ratio input listener: updates interpretation helper text on input.
- Add handlers for adding custom teeth, removing custom teeth, JSON config import/export.
- Synchronize with `localStorage` (`gear_reduction_config_v2`).

#### [MODIFY] [web/js/worker.js](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/web/js/worker.js)
- Update Python bridge functions (`solve_spur_bridge`, `solve_planetary_bridge`) to handle inverted ratios, max_stages up to 6, and custom gear sets.

#### [MODIFY] [scripts/build_web_assets.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/scripts/build_web_assets.py)
- Rebuild `web/python/gear_reduction.zip` whenever core package files are updated.

---

## Verification Plan

### Automated Test Suite (`tests/`)
1. **Ratio Inversion Tests** (`tests/test_solver_exact.py`, `tests/test_cli.py`):
   - Test `"1:4"`, `"1/4"`, `"0.25"` all parse and solve to 4:1 reduction.
   - Test `"2:5"`, `"2/5"` invert to 5:2 (2.5:1).
   - Test `"4:1"`, `"10:1"` remain 4:1 and 10:1.
   - Test `"1:1"` remains 1:1 direct ratio.
2. **Prime Reachability & Stage Scaling Tests** (`tests/test_solver_stages.py`):
   - Test unreachable prime ratio (e.g. 43:1 with inventory 9-40T) returns `[]` immediately in exact mode without hanging.
   - Test prime ratio in approximate mode finds closest rational train.
   - Test 5-stage and 6-stage solutions for large composite ratios (e.g. 1000:1 or 2400:1).
3. **Known vs. Available Inventory & Custom Sizes Tests** (`tests/test_config.py`):
   - Test 9T and 10T are included in defaults.
   - Test adding custom size (e.g. 52T) without intermediate sizes (41T–51T).
   - Test JSON configuration export and loading with known vs available teeth.
4. **Web Bundle & Schema Tests** (`tests/test_web_bundle.py`, `tests/test_schema.py`):
   - Verify `scripts/build_web_assets.py` produces updated zip archive.
   - Verify all 5-stage and 6-stage outputs strictly adhere to `gear_reduction_solution.schema.json`.

Run command:
```bash
PYTHONPATH=src:. pytest -v
```

### Manual Verification
1. Launch local test server (`python3 -m http.server -d web 8000`).
2. Test entering `1:4` in Spur and Planetary tabs; verify it calculates 4:1 solution.
3. Test selecting 5 and 6 stages for a large ratio.
4. Open Gear Teeth Inventory dialog:
   - Verify 9T and 10T are present.
   - Add custom gear size `52T`; verify button appears in matrix.
   - Test solving with `52T` gear in active set.
   - Test Export JSON and Import JSON functions.
