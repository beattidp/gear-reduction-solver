# gear-reduction-solver

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![WebAssembly Pyodide](https://img.shields.io/badge/WebAssembly-Pyodide_0.26-yellowgreen.svg)](https://pyodide.org/)
[![Tests](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)]()
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-deployed-success.svg)](https://beattidp.github.io/gear-reduction-solver/)

An engineering-grade kinematic synthesis and optimization solver for mechanical speed reduction gear trains. Solves for optimal compound spur trains, single-start worm drives, and multi-stage epicyclic (planetary) gearboxes using exact rational mathematics and physical assembly constraints.

Runs both as a scriptable command-line interface (CLI) and as a 100% client-side web application in the browser via Pyodide / WebAssembly with zero server-side computation.

---

### 🚀 Live Web Application

Try the interactive solver directly in your browser:  
👉 **[https://beattidp.github.io/gear-reduction-solver/](https://beattidp.github.io/gear-reduction-solver/)**

---

## Key Features

### 1. Compound Spur & Worm Train Solver
- **Exact Rational Arithmetic**: Uses `fractions.Fraction` throughout the core algorithm to eliminate floating-point rounding errors during factorization and stage synthesis.
- **Single-Start Worm Drive Support**: Optionally drives the first reduction stage with a worm screw ($1\text{T}$ pinion) for compact high-ratio reduction.
- **Weighted Fabrication Cost Model**: Weights worm wheel teeth ($3.0\times$) so compact worm wheels are naturally prioritized over unnecessarily large wheels.
- **Progressive Torque Load Ordering**: Sorts driven gears in non-decreasing tooth count order ($G_1 \le G_2 \le \dots$) to withstand increasing stage torque loads.
- **BOM Deduplication**: Identifies identical physical gear inventories and eliminates duplicate permutations.
- **Minimal Stage Depth Termination**: Stops combinatorial search immediately once the minimal stage depth yields exact solutions.
- **Bounded Approximation Fallback**: Returns the closest mechanical approximations when prime or fractional ratios cannot be reached exactly.

### 2. Epicyclic / Planetary Gear Train Solver
- **Fundamental Willis Equation Kinematics**: Models all three canonical speed reduction stator configurations:
  - **Outer Ring Fixed (Stator = Ring)**: Input = Sun, Output = Carrier $\rightarrow$ High-ratio speed reduction ($\text{Ratio} = 1 + R/S > 2.0$, forward rotation).
  - **Carrier Fixed (Stator = Carrier Pins)**: Input = Sun, Output = Ring $\rightarrow$ Moderate-ratio reduction with inverted rotation ($\text{Ratio} = R/S > 1.0$, reverse rotation).
  - **Sun Fixed (Stator = Sun Gear)**: Input = Ring, Output = Carrier $\rightarrow$ Low-ratio reduction ($1.0 < \text{Ratio} = 1 + S/R < 2.0$, forward rotation).
- **Physical Assembly & Geometric Invariants**:
  - **Coaxiality Condition**: $R = S + 2P$ (ensures concentric sun and ring pitch diameters).
  - **Symmetrical Meshing / Assembly Condition**: $(S + R) \pmod N == 0$ (for $N$ equally spaced planets, default $N=3$).
  - **Adjacent Planet Tip Clearance**: $(S + P) \sin(\pi / N) > P + 2$ (prevents adjacent planet teeth interference).
- **Multi-Stage Cascaded Planetary Systems**: Cascades planetary stages (e.g., carrier output driving subsequent sun input) for high-reduction compact drives.

### 3. 100% Client-Side Web Application (Pyodide / WebAssembly)
- **Zero Server Overhead**: The web app runs entirely client-side; GitHub Pages only delivers static HTML, CSS, JS, and a 22 KB Python zip archive.
- **Dedicated Web Worker**: The Pyodide WASM runtime executes in a background thread, keeping the user interface smooth and responsive during computation.
- **Multi-Tabbed UI**: Built according to Modern Web Guidance with dedicated tabs for Spur/Worm and Planetary gear systems.
- **Interactive Gear Tooth Inventory Modal**: Native `<dialog>` modal allowing real-time toggling of available gear sizes (11T–40T), persisted in browser `localStorage`.
- **Export Capabilities**: Easily copy solution sets as structured JSON or inspection tables.

---

## Quick Start: Web Application

### Running Locally
To launch the client-side web application locally with Python's built-in static HTTP server:

```bash
python3 -m http.server 8000 --directory web
```

Then open your browser to:  
👉 `http://localhost:8000`

---

## Quick Start: Command-Line Interface (CLI)

### Installation
Clone the repository and install test/development dependencies:

```bash
git clone https://github.com/beattidp/gear-reduction-solver.git
cd gear-reduction-solver
pip install -r requirements.txt
```

### CLI Usage Examples

#### 1. Compound Spur Train (Exact Ratio)
Calculate the 3 cheapest gear trains achieving a 10:1 reduction using available teeth (11–40T):
```bash
python3 -m gear_reduction.cli -r 10:1
```
Output:
```
=== Spur / Worm Gear Reduction Solutions for Target Ratio 10:1 ===
#   | Stages (Pinion -> Gear)                | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
--------------------------------------------------------------------------------------------
1   | [11T -> 33T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 196    | 1.0000
2   | [12T -> 36T] [12T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 200    | 1.0204
3   | [12T -> 39T] [13T -> 40T]              | 10/1 (10.0000)   | 0.00%    | 204    | 1.0408
--------------------------------------------------------------------------------------------
Found 3 solution(s). Sorted from lowest to highest relative cost.
```

#### 2. Worm Drive Input Stage
Calculate reduction using a single-start worm on stage 1:
```bash
python3 -m gear_reduction.cli -r 60:1 --worm
```

#### 3. Epicyclic / Planetary Gear Solver
Find single or multi-stage planetary configurations for 4:1:
```bash
python3 -m gear_reduction.cli -r 4:1 --planetary
```
Output:
```
=== Planetary Gear Reduction Solutions for Target Ratio 4:1 ===
#   | Configuration [Stator: S / P / R]              | Achieved Ratio   | Dev %    | Cost   | Rel. Cost 
----------------------------------------------------------------------------------------------------
1   | [Ring Fixed: S=12T P=12Tx3 R=36T]              | 4/1 (4.0000)     | 0.00%    | 162    | 1.0000
2   | [Ring Fixed: S=15T P=15Tx3 R=45T]              | 4/1 (4.0000)     | 0.00%    | 188    | 1.1605
3   | [Carrier Fixed: S=12T P=18Tx3 R=48T (Rev)]     | 4/1 (4.0000)     | 0.00%    | 198    | 1.2222
----------------------------------------------------------------------------------------------------
Found 3 planetary solution(s). Sorted from lowest to highest relative cost.
```

#### 4. Filter by Planetary Stator Configuration
Force carrier-fixed inverted rotation:
```bash
python3 -m gear_reduction.cli -r 3:1 --planetary --stator carrier
```

#### 5. Comparative Evaluation (`--type all`)
Evaluate both Spur/Worm and Planetary solutions side-by-side:
```bash
python3 -m gear_reduction.cli -r 10:1 --type all
```

#### 6. Structured JSON Output
Generate machine-readable JSON for integration into CAD or robotics toolchains:
```bash
python3 -m gear_reduction.cli -r 10:1 --planetary --json
```

---

## Project Architecture

```
gear-reduction-solver/
├── config/
│   └── default_config.json      # Default tooth inventory and cost weighting schema
├── doc/
│   ├── features/                # Comprehensive technical feature documentation
│   ├── proposals/               # Implementation proposals and architecture designs
│   ├── walkthroughs/            # Milestone walkthroughs and verification summaries
│   └── worklogs/                # Detailed chronological development worklogs
├── scripts/
│   └── build_web_assets.py      # Packages Python core into web/python/gear_reduction.zip
├── src/
│   └── gear_reduction/
│       ├── cli.py               # Command-line interface with formatted tables and JSON
│       ├── config.py            # Configuration loader and dataclass models
│       └── core/
│           ├── models.py        # Spur & worm domain models, CostModel, ReductionSolution
│           ├── solver.py        # Exact Meet-in-the-Middle and approximate solver
│           ├── planetary.py     # Planetary domain models, Willis kinematics, clearances
│           └── planetary_solver.py # Planetary single-stage & multi-stage cascade solver
├── tests/
│   ├── test_cli.py              # CLI option parsing, output tables, and JSON
│   ├── test_models.py           # Domain models, physical validation, cost calculation
│   ├── test_planetary.py        # Planetary kinematics, geometry, and solver tests
│   ├── test_solver_approx.py    # Bounded approximate search tests
│   ├── test_solver_exact.py     # Exact Meet-in-the-Middle reduction tests
│   └── test_web_bundle.py       # Web assets packaging and Pyodide worker bridge tests
└── web/
    ├── index.html               # Responsive HTML5 UI with tabs and native dialogs
    ├── css/style.css            # Modern responsive CSS design system
    ├── js/app.js                # Main thread UI controller and state manager
    ├── js/worker.js             # Dedicated Web Worker hosting Pyodide WebAssembly
    └── python/
        └── gear_reduction.zip   # Bundled pure-Python package for browser execution
```

---

## Testing & Quality Assurance

The project contains 53 automated tests covering domain modeling, geometric checks, kinematics, search algorithms, CLI output, and web asset integrity:

```bash
PYTHONPATH="src:." pytest -v tests/
```

---

### Credit where Credit is Due:
The code for this application was developed with [Google Antigravity](http://antigravity.google/).  _Thank you!_
