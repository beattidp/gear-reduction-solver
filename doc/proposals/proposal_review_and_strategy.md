# Gear Reduction Solver — Technical Review, Strategy & Framework Recommendations

**Date**: 2026-11-10  
**Document Status**: Proposal & Technical Recommendation  
**Reference Document**: [`.proposal`](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/.proposal)

---

## 1. Executive Summary & Problem Analysis

The objective is to design and implement a **Gear Reduction Solver** application that determines optimal multi-stage compound gear trains to achieve a specified reduction ratio $[in : out]$ given a constrained inventory of gears (defaulting to $11T$ through $40T$, with an optional single-start worm drive input stage).

### Core Functional Requirements & Constraints
1. **Target Reduction Ratio**: Specified as $[in : out]$ (e.g., $10:1$, $25:2$, etc.).
2. **Gear Pair Constraint**: In each stage, the driving gear (pinion $P$) must be smaller than or equal to the driven gear ($G$): $P \le G$.
3. **Worm Drive Option**:
   - When enabled, the first stage is driven by a single-start worm: stage 1 is `{pinion: 1, gear: selectedWormGear}`.
   - The selected worm gear must come from the available gear set.
   - The worm stage must always be listed as the first pair in the solution.
4. **Exact vs. Approximate Modes**:
   - Exact solutions only by default. If no exact solution exists, approximate solutions must **not** be presented unless explicitly enabled by the user.
   - In approximate mode, find the solutions with achieved ratio as close as possible to the target ratio.
   - Approximate solutions must compute and report `deviationPercentage`:
     $$\text{deviationPercentage} = \left|\frac{\text{achievedRatio} - \text{targetRatio}}{\text{targetRatio}}\right| \times 100\%$$
     Formatted to two decimal places (e.g., `"0.52%"`).
5. **Costing & Optimization Model**:
   - Absolute cost formula:
     $$\text{Cost} = \sum_{i=1}^{k} (P_i + G_i) + (50 \times k)$$
     where $k$ is the number of gear pairs (stages) in the train.
   - Relative cost weight:
     $$\text{relativeCost} = \frac{\text{current\_solution\_cost}}{\text{lowest\_solution\_cost}}$$
     (Lowest cost solution has relative cost $= 1.0$).
6. **Solution Uniqueness & Canonical Ordering**:
   - Stage order does not alter the total reduction ratio ($\prod \frac{G_i}{P_i}$).
   - Any permutation of identical spur gear pairs is considered a duplicate; only **one** unique combination must be returned.
   - Canonical sorting within each solution: Sort stages in ascending order of pinion tooth count (breaking ties by driven gear tooth count).
   - If a worm drive is present, it is locked as stage 1 regardless of tooth counts.
   - Output solutions must be sorted from lowest `relativeCost` to highest `relativeCost`, capped at user-defined maximum (default: 3).

---

## 2. Algorithmic Strategy

A brute-force permutation search would experience exponential slowdown as maximum stages increase. Because gear trains typically require between 1 and 4 stages for standard mechanisms, we design a mathematically sound, pruned combinatorial solver.

```
                  Target Ratio [in : out]
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      Worm Stage Enabled?         Direct Spur Train
      Stage 1: (1, G_worm)        All stages: (P_i, G_i)
              │                           │
              └─────────────┬─────────────┘
                            ▼
              Exact Rational Factorization
               (Iterative Depth 1 to 4)
             Pruning via Branch & Bound
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        Exact Found?                No Exact Found?
              │                           │
     Return Lowest Cost          Approximate Allowed?
      Unique Solutions                    │
                                ┌─────────┴─────────┐
                                ▼                   ▼
                             [Yes]                 [No]
                     Bounded Best-First      Return "No Exact
                      Priority Queue          Solution Found"
                     (Min Deviation &
                        Min Cost)
```

### A. Stage Pair Generation & Canonical Symmetry Breaking
- **Pair Space**: Given available teeth set $T \subset [T_{\min}, T_{\max}]$, generate candidate spur pairs:
  $$\mathcal{S} = \{(P, G) \in T \times T \mid P \le G\}$$
  For $T = \{11, \dots, 40\}$, $|\mathcal{S}| = \frac{30 \times 31}{2} = 465$ possible pairs.
- **Symmetry Elimination**: Because stages commute multiplicatively ($\frac{G_1}{P_1} \times \frac{G_2}{P_2} = \frac{G_2}{P_2} \times \frac{G_1}{P_1}$), multi-stage trains must be generated as **combinations with replacement** of pairs from $\mathcal{S}$, sorted canonically ($P_1 \le P_2 \le \dots \le P_k$). This eliminates $k!$ redundant evaluations per solution.

### B. Exact Solver: Exact Rational Arithmetic (`fractions.Fraction`)
- Use Python's built-in `fractions.Fraction` to avoid floating-point rounding issues when verifying exact ratios.
- Search progressively by stage depth ($k = 1, 2, 3, 4$):
  - In practice, a 5-stage train adds $5 \times 50 = 250$ in stage penalties alone, making it cost-ineffective compared to 1–3 stage trains for reachable ratios.
  - For each depth $k$, find exact matches where $\prod_{i=1}^k \frac{G_i}{P_i} = R_{\text{target}}$.
  - If solutions are found at depth $k$, evaluate costs and prune deeper searches if deeper stages cannot beat the best cost.

### C. Approximate Solver: Multi-Objective Pruned Search
- When no exact solution exists and approximate mode is enabled:
  - Track candidates in a bounded priority queue (or min-heap) ordered by:
    1. Primary key: Absolute ratio error $|R_{\text{achieved}} - R_{\text{target}}|$
    2. Secondary key: Train cost
  - Limit candidate stages using branch-and-bound (e.g., pruning paths where accumulated partial ratio diverges beyond achievable single-stage bounds).
  - Format output with the required `deviationPercentage` formula.

---

## 3. Recommended Technology Stack & Architecture

To satisfy modularity, maintainability, clean testing, and user configuration, a 3-tier decoupled architecture is recommended:

```
┌────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│   • PySide6 (Desktop GUI) - Native, Clean Selection    │
│   • CLI / Rich Terminal Interface (Batch & Scripting)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Application Layer                   │
│   • Configuration Loader (JSON defaults / presets)     │
│   • ReductionSolver Orchestrator & Exporters (JSON/CSV)│
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Core Domain Layer                   │
│   • CostModel (Teeth sum + 50 * stages penalty)        │
│   • GearPair (Pinion, Gear, validation, ratios)        │
│   • GearTrain / ReductionSolution (Canonical sorting,   │
│     relative cost weights, deviationPercentage)        │
│   • Factorizer & Combinatorial Search Engine           │
└────────────────────────────────────────────────────────┘
```

### A. Python & Core Libraries
- **Language**: Python 3.10+ (utilizing dataclasses, type hints, match-case, `fractions.Fraction`, `itertools`, `math`).
- **Data Validation & Config**: Standard library `dataclasses` + `json` for zero-overhead validation and configuration management.
- **Testing**: `pytest` for rigorous parameterized unit and regression testing.

### B. UI Framework Evaluation
The proposal mentions:
> *"Available pinion and gear sizes (by number of teeth): a list of gear sizes to use, plus a selection dialog with 11 to 40 teeth (11T, 12T, ... 40T), with all enabled by default."*

| Framework | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- |
| **PySide6 (Qt for Python)** | • Professional engineering look & feel.<br>• Native dialogs, grid layouts for 11T–40T toggle chips/checkboxes.<br>• High-performance interactive tables with sorting.<br>• Easily packages into desktop binary (`pyinstaller`). | Requires GUI display server (X11/Wayland/Windows). | **Recommended Primary GUI** |
| **NiceGUI / Streamlit / FastAPI+Web** | • Runs in any browser, zero OS UI dependencies.<br>• Can render interactive SVG gear train diagrams.<br>• Remote or local access. | Overhead of web server lifecycle for a standalone desktop calculation utility. | **Strong Alternative (Web)** |
| **Rich + Typer (CLI)** | • Instant execution, scriptable, no GUI required.<br>• Formatted tables, colors, JSON output mode for pipelines. | Not a graphical dialog for selecting teeth checkboxes. | **Recommended Secondary Interface (CLI)** |

**Dual-Interface Recommendation**:
1. Implement the **Core Solver Engine** in `src/gear_reduction/core/` with zero GUI dependencies.
2. Provide a **CLI interface** (`src/gear_reduction/cli/`) for automated test runs, headless workflows, and scripting.
3. Provide a **PySide6 Desktop Application** (`src/gear_reduction/gui/`) featuring:
   - Input controls for target ratio $[in : out]$, max solutions, and worm gear toggle.
   - Gear Tooth Selection Panel: Grid of toggleable badges/checkboxes for 11T–40T with "Select All", "Deselect All", and "Invert" buttons.
   - Solution Results Table: Displays stages, achieved ratio, deviation %, absolute cost, relative cost weight, and export to CSV/JSON.

---

## 4. Configuration & Presets (JSON)

To fulfill *"Initial minimum gear size is 11 teeth, and maximum gear size is 40 teeth. This could potentially be configurable with JSON configuration file"*, we will define a clean configuration schema:

```json
{
  "min_gear_teeth": 11,
  "max_gear_teeth": 40,
  "default_enabled_teeth": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40],
  "cost_model": {
    "stage_penalty": 50,
    "teeth_cost_multiplier": 1.0
  },
  "solver_defaults": {
    "max_solutions": 3,
    "allow_approximate": false,
    "max_stages": 4
  }
}
```

---

## 5. Verification & Testing Strategy

In adherence to the project's Python engineering guidelines (`~/.gemini/config/skills/python/SKILL.md`):
1. **Cost Model Verification**:
   - Unit test single-stage, two-stage, and three-stage costs against exact manual sums.
   - Verify relative cost calculation where the cheapest solution is guaranteed to be $1.00$ and others $\ge 1.00$.
2. **Canonical Ordering & Uniqueness Verification**:
   - Verify that permuted equivalent trains produce a single unique representation.
   - Verify that pairs are sorted ascending by pinion tooth count.
   - Verify that worm drive $(1, G_{\text{worm}})$ is always stage 1.
3. **Exact vs. Approximate Verification**:
   - Test cases where exact solutions exist (e.g. $10:1 \implies (12, 24) \times (11, 55)$ or direct factors).
   - Test prime ratio cases (e.g. $71:1$ with gears up to $40T$) where exact solutions are impossible:
     - Verify solver returns empty / "No exact solution" when approximate mode is disabled.
     - Verify solver returns closest solutions with correct `deviationPercentage` when approximate mode is enabled.
4. **Performance Benchmarking**:
   - Ensure typical queries solve within $< 100$ milliseconds.

---

## 6. Phased Implementation Roadmap

1. **Phase 1: Core Domain & Solver (`src/gear_reduction/core/`)**
   - Data models (`GearPair`, `GearTrain`, `Solution`, `CostModel`).
   - Pure combinatorial and rational solver algorithm.
   - Full suite of pytest unit tests in `tests/test_core.py`.
2. **Phase 2: Configuration & CLI (`src/gear_reduction/cli/`)**
   - JSON config loader and CLI interface with formatted table output.
   - Export functionality (JSON / text report).
3. **Phase 3: GUI Application (`src/gear_reduction/gui/`)**
   - PySide6 application with tooth selection dialog/panel, input forms, and reactive results view.
4. **Phase 4: Documentation & Packaging**
   - User manual, API documentation in `doc/features/`, and packaging.
