# Feature Documentation: Client-Side Web Application (Pyodide WebAssembly)

## Overview
Phase 2 delivers a 100% client-side web application for the Gear Reduction Solver. The application runs entirely inside the user's web browser using **Pyodide (WebAssembly CPython 3.12)** running inside a dedicated background **Web Worker**. The web app requires zero server-side computation and can be hosted statically on GitHub Pages or run locally with any basic file server (`python3 -m http.server 8000 --directory web`).

---

## Architecture & Data Flow

```
User Web Browser
┌────────────────────────────────────────────────────────────────────────┐
│ Main UI Thread (web/index.html + web/js/app.js)                        │
│ ┌──────────────────────────┐  ┌──────────────────────────────────────┐ │
│ │ Header & Gear Inventory  │  │ Tab 1: Spur / Worm Solver            │ │
│ │ (11T-40T <dialog> Modal) │  │ Tab 2: Planetary Gear Solver         │ │
│ └──────────────────────────┘  └──────────────────────────────────────┘ │
│                                      │                                 │
│                   PostMessage ({id, type, payload})                    │
│                                      ▼                                 │
│ Web Worker (web/js/worker.js)                                          │
│  • Pyodide WASM Runtime (CPython 3.12 WebAssembly from jsDelivr CDN)   │
│  • web/python/gear_reduction.zip (~22 KB, unpacked via unpackArchive)  │
│  • Executes ReductionSolver and PlanetarySolver in background          │
│  • Returns structured JSON solutions without blocking the main UI      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Features & UI Components

### 1. Multi-Solver Tabbed Interface
Conforming to Modern Web Guidance (`role="tablist"`, `aria-selected`, accessible underline indicator):
- **Tab 1: Spur & Worm Train Solver**:
  - Target reduction ratio input with quick-fill presets (`4:1`, `10:1`, `31:1`, `60:1`).
  - Single-start worm input stage toggle.
  - Approximation toggle, max stages, max solutions, and worm gear multiplier cost tuning.
  - Interactive results table with stage pills, achieved rational fractions, decimal representations, deviation %, and cost metrics.
- **Tab 2: Planetary Gear Train Solver**:
  - Target reduction ratio input with quick-fill presets (`3:1`, `4:1`, `10:1`, `16:1`).
  - Stator configuration segmented selector (`Any (Optimal)`, `Ring Fixed (>2:1)`, `Carrier Fixed (Inverted)`, `Sun Fixed (1–2:1)`).
  - Planet gears count selector ($N=2, 3, 4$), max stages, max solutions.
  - Advanced options: Ring gear multiplier, max ring teeth, strict ring inventory toggle.
  - Interactive results table highlighting stator arrangement, forward/reverse rotation direction badge, and relative cost ranking.

### 2. Available Gear Teeth Inventory Modal
- Accessible native `<dialog>` element with `overscroll-behavior: contain`.
- Interactive matrix of gear tooth toggle buttons (11T through 40T).
- Live active gear count badge (e.g. `30/30 active`).
- "Select All", "Deselect All", and "Reset (11–40T)" toolbar controls.
- Automatic persistence to browser `localStorage` across page visits.

### 3. Background Web Worker Integration
- Pyodide WebAssembly engine loads in the background (`web/js/worker.js`).
- Dynamic status pill in the header displays engine states:
  - `Loading WASM...` (flashing amber indicator).
  - `WASM Solver Ready` (solid emerald indicator).
- All combinatorial searches execute asynchronously off the main thread, keeping inputs, tab switches, and dialogs 100% smooth.

### 4. Zero-Server Static Hosting & GitHub Pages
- Hosted out of the `web/` directory.
- Bundled pure-Python zip archive (`web/python/gear_reduction.zip`, ~22 KB) created automatically by `scripts/build_web_assets.py`.
- Automated GitHub Actions deployment workflow: `.github/workflows/deploy-pages.yml`.

---

## How to Run Locally

Start a local static server from the project directory:
```bash
python3 -m http.server 8000 --directory web
```
Then navigate to:
```
http://localhost:8000
```

---

## Automated Verification
Run the automated test suite:
```bash
PYTHONPATH="src:." pytest -v tests/test_web_bundle.py
```
- Total project tests: 53 passed with 0 failures across all 5 test modules.
