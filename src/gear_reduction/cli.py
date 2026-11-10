"""Command-line interface for the Gear Reduction Solver.

Engineering Rationale:
---------------------
Provides a headless, scriptable CLI to calculate optimal multi-stage compound
gear trains. Supports terminal-formatted summary tables and structured JSON output
for automated pipelines, testing, and external toolchain integration.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .config import SolverConfig
from .core.models import CostModel, ReductionSolution
from .core.solver import ReductionSolver, parse_ratio


def parse_teeth_arg(teeth_str: str) -> list[int]:
    """Parses a comma-separated or range-based teeth string (e.g. '11-40' or '12,16,24,32')."""
    teeth: set[int] = set()
    parts = teeth_str.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                low, high = int(bounds[0]), int(bounds[1])
                teeth.update(range(min(low, high), max(low, high) + 1))
            else:
                raise ValueError(f"Invalid tooth range '{part}'")
        elif part.isdigit():
            teeth.add(int(part))
        else:
            raise ValueError(f"Invalid tooth count '{part}'")
    return sorted(list(teeth))


def format_stage(pinion: int, gear: int, is_worm: bool) -> str:
    """Formats a single gear pair for display."""
    if is_worm:
        return f"[Worm(1T) -> {gear}T]"
    return f"[{pinion}T -> {gear}T]"


def format_table(solutions: Sequence[ReductionSolution], target_ratio_str: str) -> str:
    """Generates a formatted ASCII table representing the calculated solutions."""
    if not solutions:
        return f"\nNo gear reduction solutions found for target ratio {target_ratio_str}.\n"

    lines: list[str] = [
        "",
        f"=== Gear Reduction Solutions for Target Ratio {target_ratio_str} ===",
        f"{'#':<3} | {'Stages (Pinion -> Gear)':<38} | {'Achieved Ratio':<16} | {'Dev %':<8} | {'Cost':<6} | {'Rel. Cost':<10}",
        "-" * 92,
    ]

    for idx, sol in enumerate(solutions, start=1):
        stages_str = " ".join(
            format_stage(s.pinion, s.gear, s.is_worm) for s in sol.stages
        )
        frac_str = f"{sol.achieved_ratio.numerator}/{sol.achieved_ratio.denominator}"
        ratio_display = f"{frac_str} ({float(sol.achieved_ratio):.4f})"
        dev_str = sol.deviation_percentage if sol.deviation_percentage else "0.00%"
        lines.append(
            f"{idx:<3} | {stages_str:<38} | {ratio_display:<16} | {dev_str:<8} | {sol.cost:<6} | {sol.relative_cost:.4f}"
        )

    lines.append("-" * 92)
    lines.append(f"Found {len(solutions)} solution(s). Sorted from lowest to highest relative cost.\n")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for gear reduction solver."""
    parser = argparse.ArgumentParser(
        prog="gear-reduction-solver",
        description="Calculate optimal gear reduction solutions for gear train design.",
    )
    parser.add_argument(
        "-r",
        "--ratio",
        required=True,
        help="Target reduction ratio (e.g. '10:1', '25:2', '12.5').",
    )
    parser.add_argument(
        "-w",
        "--worm",
        action="store_true",
        help="Use a single-start worm to drive the first gear stage.",
    )
    parser.add_argument(
        "-a",
        "--approx",
        action="store_true",
        help="Allow approximate solutions if no exact solution is possible.",
    )
    parser.add_argument(
        "-n",
        "--max-solutions",
        type=int,
        default=3,
        help="Maximum number of solutions to return (default: 3).",
    )
    parser.add_argument(
        "-s",
        "--max-stages",
        type=int,
        default=4,
        help="Maximum number of gear stages to consider (default: 4).",
    )
    parser.add_argument(
        "-t",
        "--teeth",
        help="Available gear teeth (e.g. '11-40' or '11,12,14,16,20,24,30,40'). Defaults to 11-40.",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to custom JSON configuration file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format.",
    )

    args = parser.parse_args(argv)

    try:
        cfg = SolverConfig.load(args.config)
        available_teeth = cfg.default_enabled_teeth
        if args.teeth:
            available_teeth = parse_teeth_arg(args.teeth)

        target_frac = parse_ratio(args.ratio)

        solver = ReductionSolver(
            available_teeth=available_teeth,
            cost_model=cfg.cost_model,
            max_stages=args.max_stages,
        )

        solutions = solver.solve(
            target_ratio=target_frac,
            use_worm=args.worm or cfg.use_worm,
            allow_approximate=args.approx or cfg.allow_approximate,
            max_solutions=args.max_solutions or cfg.max_solutions,
        )

        if args.json:
            output_data = {
                "target_ratio": f"{target_frac.numerator}/{target_frac.denominator}",
                "target_ratio_float": float(target_frac),
                "use_worm": args.worm or cfg.use_worm,
                "allow_approximate": args.approx or cfg.allow_approximate,
                "solutions_count": len(solutions),
                "solutions": [sol.to_dict() for sol in solutions],
            }
            print(json.dumps(output_data, indent=2))
        else:
            print(format_table(solutions, args.ratio))

        return 0 if solutions else 1

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
