# Phase 2: Client-Side Web Application (Pyodide / WebAssembly)

Build a 100% client-side web application hosted statically on GitHub Pages (and runnable locally via `python3 -m http.server --directory docs`). The application executes the Python core solver directly in the user's browser via **Pyodide (WebAssembly CPython)** running inside a dedicated Web Worker.

---

## User Review Required

> [!IMPORTANT]
> **Deployment Directory (`docs/`)**:
> GitHub Pages natively supports serving static websites from the `/docs` folder on the `main` branch. We will place all static web assets (HTML, CSS, JS, Pyodide worker, and bundled Python code) in `docs/` so that pushing to GitHub immediately deploys the site without requiring complex build pipelines.
> 
> Local execution will be available instantly with:
> ```bash
> python3 -m http.server 8000 --directory docs
> ```

> [!NOTE]
> **UI Layout & Navigation (Tabs)**:
> As requested, the UI will feature two primary tabs:
> 1. **Spur & Worm Train Solver**: Cascaded compound gear trains and single-start worm drives.
> 2. **Planetary Gear Solver**: Epicyclic gear arrangements across Ring, Carrier, and Sun stator configurations.
> 
> Both tabs share a global gear tooth inventory dialog (11T–40T matrix) accessible from the header.

---

## Open Questions

> [!TIP]
> **Pyodide CDN vs. Offline Bundle**:
> Pyodide's WebAssembly runtime will be fetched on first load from jsDelivr CDN (`https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js`) and cached by the browser's HTTP cache. The pure-Python `gear_reduction` package will be packaged as a lightweight zip archive (`docs/python/gear_reduction.zip`, ~25 KB) and unpacked in the worker via Pyodide's native `unpackArchive()` API.
> 
> Please confirm if loading Pyodide from CDN meets your expectations for GitHub Pages deployment.

---

## Architecture Overview

```
User Browser
┌────────────────────────────────────────────────────────────────────────┐
│ Main UI Thread (docs/index.html + docs/js/app.js)                      │
│ ┌──────────────────────────┐  ┌──────────────────────────────────────┐ │
│ │ Header & Gear Inventory  │  │ Tab 1: Spur / Worm Solver            │ │
│ │ (11T-40T <dialog> Modal) │  │ Tab 2: Planetary Gear Solver         │ │
│ └──────────────────────────┘  └──────────────────────────────────────┘ │
│                                      │                                 │
│                   PostMessage ({task, args})                           │
│                                      ▼                                 │
│ Web Worker (docs/js/worker.js)                                         │
│  • Pyodide WASM Runtime (CPython 3.12 WebAssembly)                     │
│  • docs/python/gear_reduction.zip (unpacked into /gear_reduction)       │
│  • Executes ReductionSolver and PlanetarySolver in background          │
│  • Returns structured JSON results without blocking main thread UI     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Proposed Changes

### Build & Packaging Utilities

#### [NEW] [build_web_assets.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/scripts/build_web_assets.py)
- Script that bundles `src/gear_reduction` into `docs/python/gear_reduction.zip` so web assets stay in sync with Python core improvements.

---

### Web Application (`docs/`)

#### [NEW] [index.html](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/docs/index.html)
- Responsive, modern HTML5 structure adhering to Modern Web Guidance:
  - Header with app title, status indicator ("WASM Engine: Initializing / Ready"), and "Gear Inventory (11-40T)" button.
  - Tablist with `role="tablist"` and tabs: `Spur & Worm Train` and `Planetary Gear Train`.
  - Tabpanel 1: Spur & Worm inputs (ratio, worm checkbox, max stages, max solutions, worm multiplier) and results table.
  - Tabpanel 2: Planetary inputs (ratio, stator selector, planet count, ring multiplier, max ring teeth, strict ring toggle) and results table.
  - Native `<dialog>` modal for tooth selection matrix (11 to 40 toggle buttons, Select All, Deselect All, Reset).
  - Copy JSON and Table export buttons.

#### [NEW] [style.css](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/docs/css/style.css)
- Clean, responsive CSS with modern variables (colors, spacing, shadows).
- Glassmorphism header, card layouts, accessible contrast (WCAG 2.1 AA compliant).
- Dialog styling with `overscroll-behavior: contain` and modal backdrop.
- Interactive tooth grid styling (toggled active/inactive states with visual indicators).
- Table layout with sticky headers and responsive horizontal scroll.

#### [NEW] [app.js](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/docs/js/app.js)
- UI state management:
  - Active tab switching (selection follows focus / click).
  - Gear inventory state (persisted to `localStorage`).
  - Form validation for ratio inputs (`10:1`, `25:2`, `12.5`).
  - Dispatches solve requests to the Web Worker via `worker.postMessage()`.
  - Renders solution cards, tables, badges, and error alerts.

#### [NEW] [worker.js](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/docs/js/worker.js)
- Web Worker dedicated to Pyodide:
  - Loads Pyodide from CDN on worker start.
  - Unpacks `gear_reduction.zip` into the Pyodide filesystem.
  - Exposes Python execution wrapper returning JSON data.
  - Handles `solve_spur` and `solve_planetary` messages and posts results back to main thread.

---

### Tests & Verification

#### [NEW] [test_web_bundle.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/tests/test_web_bundle.py)
- Automated Python test verifying:
  - `docs/` folder structure contains all necessary assets (`index.html`, `css/style.css`, `js/app.js`, `js/worker.js`, `python/gear_reduction.zip`).
  - `gear_reduction.zip` contains valid Python byte-identical source files matching `src/gear_reduction/`.
  - Simulates the worker Python runner script to ensure Pyodide execution string executes without syntax errors.

---

## Verification Plan

### Automated Tests
1. Test packaging and static bundle integrity:
   ```bash
   PYTHONPATH=src pytest -v tests/test_web_bundle.py
   PYTHONPATH=src pytest -v tests/
   ```

### Manual Verification
1. Launch local static server:
   ```bash
   python3 -m http.server 8000 --directory docs
   ```
2. Open `http://localhost:8000` in browser.
3. Test Spur/Worm tab:
   - Enter `10:1` $\rightarrow$ verify 3 solutions match CLI.
   - Toggle Worm Drive with `60:1` $\rightarrow$ verify 18T/20T worm wheel solutions appear.
4. Test Planetary tab:
   - Enter `4:1` $\rightarrow$ verify Ring Fixed ($12\text{T}/12\text{T}/36\text{T}$) and Carrier Fixed solutions.
   - Filter by Stator (`Carrier Fixed`) for `3:1` $\rightarrow$ verify inverted output badge.
5. Test Gear Inventory modal:
   - Disable 11T and 12T gears $\rightarrow$ rerun `10:1` $\rightarrow$ verify solutions adapt to available inventory.
