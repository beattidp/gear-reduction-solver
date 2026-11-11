"""Command-line interface for the Gear Reduction Solver.

Engineering Rationale:
---------------------
Provides a headless, scriptable CLI to calculate optimal multi-stage compound
gear trains (spur, worm, and epicyclic/planetary systems). Supports terminal-formatted
summary tables and structured JSON output for automated pipelines, testing,
and external toolchain integration.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .config import SolverConfig
from .core.models import CostModel, ReductionSolution
from .core.planetary import (
    PlanetaryCostModel,
    PlanetarySolution,
    PlanetaryStage,
    PlanetaryStator,
)
from .core.planetary_solver import PlanetarySolver
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


def format_planetary_stage(stage: PlanetaryStage) -> str:
    """Formats a single planetary stage for display."""
    inv = " (Rev)" if stage.is_inverted else ""
    return (
        f"[{stage.stator.value.title()} Fixed: S={stage.sun}T P={stage.planet}Tx{stage.planets_count} "
        f"R={stage.ring}T{inv}]"
    )


def format_table(solutions: Sequence[ReductionSolution], target_ratio_str: str) -> str:
    """Generates a formatted ASCII table representing spur/worm gear reduction solutions."""
    if not solutions:
        return f"\nNo gear reduction solutions found for target ratio {target_ratio_str}.\n"

    lines: list[str] = [
        "",
        f"=== Spur / Worm Gear Reduction Solutions for Target Ratio {target_ratio_str} ===",
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


def format_planetary_table(solutions: Sequence[PlanetarySolution], target_ratio_str: str) -> str:
    """Generates a formatted ASCII table representing planetary gear reduction solutions."""
    if not solutions:
        return f"\nNo planetary gear reduction solutions found for target ratio {target_ratio_str}.\n"

    lines: list[str] = [
        "",
        f"=== Planetary Gear Reduction Solutions for Target Ratio {target_ratio_str} ===",
        f"{'#':<3} | {'Configuration [Stator: S / P / R]':<46} | {'Achieved Ratio':<16} | {'Dev %':<8} | {'Cost':<6} | {'Rel. Cost':<10}",
        "-" * 100,
    ]

    for idx, sol in enumerate(solutions, start=1):
        stages_str = " ".join(format_planetary_stage(s) for s in sol.stages)
        frac_str = f"{sol.achieved_ratio.numerator}/{sol.achieved_ratio.denominator}"
        ratio_display = f"{frac_str} ({float(sol.achieved_ratio):.4f})"
        dev_str = sol.deviation_percentage if sol.deviation_percentage else "0.00%"
        lines.append(
            f"{idx:<3} | {stages_str:<46} | {ratio_display:<16} | {dev_str:<8} | {sol.cost:<6} | {sol.relative_cost:.4f}"
        )

    lines.append("-" * 100)
    lines.append(f"Found {len(solutions)} planetary solution(s). Sorted from lowest to highest relative cost.\n")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for gear reduction solver."""
    parser = argparse.ArgumentParser(
        prog="gear-reduction-solver",
        description="Calculate optimal gear reduction solutions for gear train design (Spur, Worm, and Planetary).",
    )
    parser.add_argument(
        "-r",
        "--ratio",
        default=None,
        help="Target reduction ratio (e.g. '10:1', '1:4', '25:2', '1/4', '12.5'). Values < 1 automatically invert to speed reduction.",
    )
    parser.add_argument(
        "-w",
        "--worm",
        action="store_true",
        help="Use a single-start worm to drive the first gear stage (spur train solver).",
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
        help="Maximum number of gear stages to consider (1-6 for spur, 1-4 for planetary; default: 4).",
    )
    parser.add_argument(
        "-t",
        "--teeth",
        help="Available gear teeth (e.g. '9-40', '9-40,52', or '12,16,24,32'). Defaults to configured inventory.",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to custom JSON configuration file.",
    )
    parser.add_argument(
        "--config-show",
        action="store_true",
        help="Print active JSON configuration and exit.",
    )
    parser.add_argument(
        "--config-export",
        metavar="PATH",
        help="Export active configuration to specified JSON file and exit.",
    )
    parser.add_argument(
        "--worm-multiplier",
        type=float,
        help="Cost weighting factor for worm wheel teeth (default: 3.0, favors smaller worm gears).",
    )
    parser.add_argument(
        "-p",
        "--planetary",
        action="store_true",
        help="Use epicyclic/planetary gear solver.",
    )
    parser.add_argument(
        "--type",
        choices=["spur", "planetary", "all"],
        default=None,
        help="Gear system type to solve: 'spur', 'planetary', or 'all'.",
    )
    parser.add_argument(
        "--stator",
        choices=["ring", "carrier", "sun", "any"],
        default="any",
        help="For planetary solver: specify stationary member ('ring', 'carrier', 'sun', or 'any').",
    )
    parser.add_argument(
        "--planets",
        type=int,
        default=3,
        help="Number of planet gears per planetary stage (default: 3).",
    )
    parser.add_argument(
        "--ring-multiplier",
        type=float,
        help="Cost weighting multiplier for internal ring gear teeth (default: 1.5).",
    )
    parser.add_argument(
        "--max-ring-teeth",
        type=int,
        default=120,
        help="Maximum allowable teeth on internal ring gear (default: 120).",
    )
    parser.add_argument(
        "--strict-ring-inventory",
        action="store_true",
        help="Enforce that ring gear teeth must also be in available teeth inventory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format.",
    )

    args = parser.parse_args(argv)

    try:
        cfg = SolverConfig.load(args.config)

        if args.config_show:
            print(json.dumps(cfg.to_dict(), indent=2))
            return 0

        if args.config_export:
            cfg.save(args.config_export)
            print(f"Configuration exported to {args.config_export}")
            return 0

        if not args.ratio:
            parser.error("the following arguments are required: -r/--ratio")

        available_teeth = cfg.default_enabled_teeth
        if args.teeth:
            available_teeth = parse_teeth_arg(args.teeth)

        target_frac = parse_ratio(args.ratio)

        # Determine solver mode:
        solve_mode = args.type
        if solve_mode is None:
            solve_mode = "planetary" if args.planetary else "spur"

        spur_solutions: list[ReductionSolution] = []
        planetary_solutions: list[PlanetarySolution] = []

        # 1. Run Spur / Worm solver if requested
        if solve_mode in ("spur", "all"):
            cost_model = cfg.cost_model
            if args.worm_multiplier is not None:
                cost_model = CostModel(
                    stage_penalty=cfg.cost_model.stage_penalty,
                    teeth_multiplier=cfg.cost_model.teeth_multiplier,
                    worm_gear_multiplier=args.worm_multiplier,
                )

            spur_solver = ReductionSolver(
                available_teeth=available_teeth,
                cost_model=cost_model,
                max_stages=args.max_stages,
            )
            spur_solutions = spur_solver.solve(
                target_ratio=target_frac,
                use_worm=args.worm or cfg.use_worm,
                allow_approximate=args.approx or cfg.allow_approximate,
                max_solutions=args.max_solutions or cfg.max_solutions,
            )

        # 2. Run Planetary solver if requested
        if solve_mode in ("planetary", "all"):
            pcm = cfg.planetary_cost_model
            if args.ring_multiplier is not None:
                pcm = PlanetaryCostModel(
                    ring_multiplier=args.ring_multiplier,
                    stage_penalty=pcm.stage_penalty,
                    teeth_multiplier=pcm.teeth_multiplier,
                )

            planetary_solver = PlanetarySolver(
                available_teeth=available_teeth,
                cost_model=pcm,
                max_stages=min(args.max_stages, 3),
                max_ring_teeth=args.max_ring_teeth,
                planets_count=args.planets,
                strict_ring_inventory=args.strict_ring_inventory or cfg.strict_ring_inventory,
            )
            planetary_solutions = planetary_solver.solve(
                target_ratio=target_frac,
                stator=args.stator,
                allow_approximate=args.approx or cfg.allow_approximate,
                max_solutions=args.max_solutions or cfg.max_solutions,
            )

        # Format output
        has_solutions = bool(spur_solutions or planetary_solutions)

        if args.json:
            output_data: dict[str, Any] = {
                "target_ratio": f"{target_frac.numerator}/{target_frac.denominator}",
                "target_ratio_float": float(target_frac),
                "mode": solve_mode,
            }
            if solve_mode == "spur":
                output_data["solutions_count"] = len(spur_solutions)
                output_data["solutions"] = [s.to_dict() for s in spur_solutions]
            elif solve_mode == "planetary":
                output_data["solutions_count"] = len(planetary_solutions)
                output_data["solutions"] = [s.to_dict() for s in planetary_solutions]
                output_data["planetary_solutions"] = output_data["solutions"]
            else:  # all
                output_data["solutions_count"] = len(spur_solutions) + len(planetary_solutions)
                output_data["spur_solutions"] = [s.to_dict() for s in spur_solutions]
                output_data["planetary_solutions"] = [s.to_dict() for s in planetary_solutions]
            print(json.dumps(output_data, indent=2))
        else:
            if solve_mode in ("spur", "all"):
                print(format_table(spur_solutions, args.ratio))
            if solve_mode in ("planetary", "all"):
                print(format_planetary_table(planetary_solutions, args.ratio))

        return 0 if has_solutions else 1

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
