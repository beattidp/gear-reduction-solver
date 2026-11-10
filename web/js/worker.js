/**
 * Pyodide WebAssembly Web Worker for Gear Reduction Solver.
 * 
 * Runs Python combinatorial solvers in a dedicated background thread,
 * ensuring the main UI thread never blocks or freezes during calculation.
 */

/* global importScripts, loadPyodide */

const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";

let pyodideReadyPromise = null;

async function initPyodideWorker() {
    try {
        postMessage({ type: "status", message: "Loading Pyodide WebAssembly runtime..." });
        importScripts(PYODIDE_CDN);

        const pyodide = await loadPyodide();

        postMessage({ type: "status", message: "Fetching core solver package..." });
        const response = await fetch("../python/gear_reduction.zip");
        if (!response.ok) {
            throw new Error(`Failed to fetch gear_reduction.zip: ${response.statusText}`);
        }
        const zipBinary = await response.arrayBuffer();

        postMessage({ type: "status", message: "Mounting Python solver package..." });
        pyodide.unpackArchive(zipBinary, "zip");

        // Verify import and initialize python bridge
        pyodide.runPython(`
import sys
import json
from fractions import Fraction
from gear_reduction.core.models import CostModel
from gear_reduction.core.solver import ReductionSolver, parse_ratio
from gear_reduction.core.planetary import PlanetaryCostModel, PlanetaryStator
from gear_reduction.core.planetary_solver import PlanetarySolver

def solve_spur_bridge(params_json):
    params = json.loads(params_json)
    target_frac = parse_ratio(params["ratio"])
    available_teeth = params["available_teeth"]
    use_worm = params.get("use_worm", False)
    allow_approx = params.get("allow_approximate", False)
    max_solutions = params.get("max_solutions", 3)
    max_stages = params.get("max_stages", 4)
    worm_mult = params.get("worm_multiplier", 3.0)

    cost_model = CostModel(worm_gear_multiplier=worm_mult)
    solver = ReductionSolver(
        available_teeth=available_teeth,
        cost_model=cost_model,
        max_stages=max_stages
    )
    solutions = solver.solve(
        target_ratio=target_frac,
        use_worm=use_worm,
        allow_approximate=allow_approx,
        max_solutions=max_solutions
    )
    return json.dumps([s.to_dict() for s in solutions])

def solve_planetary_bridge(params_json):
    params = json.loads(params_json)
    target_frac = parse_ratio(params["ratio"])
    available_teeth = params["available_teeth"]
    stator = params.get("stator", "any")
    allow_approx = params.get("allow_approximate", False)
    max_solutions = params.get("max_solutions", 3)
    max_stages = params.get("max_stages", 3)
    ring_mult = params.get("ring_multiplier", 1.5)
    max_ring_teeth = params.get("max_ring_teeth", 120)
    planets_count = params.get("planets_count", 3)
    strict_ring = params.get("strict_ring_inventory", False)

    cost_model = PlanetaryCostModel(ring_multiplier=ring_mult)
    solver = PlanetarySolver(
        available_teeth=available_teeth,
        cost_model=cost_model,
        max_stages=max_stages,
        max_ring_teeth=max_ring_teeth,
        planets_count=planets_count,
        strict_ring_inventory=strict_ring
    )
    solutions = solver.solve(
        target_ratio=target_frac,
        stator=stator,
        allow_approximate=allow_approx,
        max_solutions=max_solutions
    )
    return json.dumps([s.to_dict() for s in solutions])
`);

        self.pyodide = pyodide;
        postMessage({ type: "ready", message: "WebAssembly solver engine initialized and ready." });
    } catch (err) {
        postMessage({ type: "error", error: err.message || String(err) });
        throw err;
    }
}

pyodideReadyPromise = initPyodideWorker();

self.onmessage = async function(event) {
    const { id, type, payload } = event.data;

    try {
        await pyodideReadyPromise;

        if (type === "solve_spur") {
            const paramsJson = JSON.stringify(payload);
            const solveFn = self.pyodide.globals.get("solve_spur_bridge");
            const resultJson = solveFn(paramsJson);
            const solutions = JSON.parse(resultJson);
            postMessage({ id, type: "result", data: solutions });
        } else if (type === "solve_planetary") {
            const paramsJson = JSON.stringify(payload);
            const solveFn = self.pyodide.globals.get("solve_planetary_bridge");
            const resultJson = solveFn(paramsJson);
            const solutions = JSON.parse(resultJson);
            postMessage({ id, type: "result", data: solutions });
        } else {
            throw new Error(`Unknown task type: ${type}`);
        }
    } catch (err) {
        postMessage({ id, type: "error", error: err.message || String(err) });
    }
};
