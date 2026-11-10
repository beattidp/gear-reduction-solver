"""Configuration loader and schema validator for Gear Reduction Solver."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .core.models import CostModel
from .core.planetary import PlanetaryCostModel


@dataclass(slots=True)
class SolverConfig:
    """Holds configuration parameters for solver execution."""

    min_gear_teeth: int = 11
    max_gear_teeth: int = 40
    default_enabled_teeth: list[int] = field(
        default_factory=lambda: list(range(11, 41))
    )
    cost_model: CostModel = field(default_factory=CostModel)
    planetary_cost_model: PlanetaryCostModel = field(default_factory=PlanetaryCostModel)
    max_solutions: int = 3
    max_stages: int = 4
    allow_approximate: bool = False
    use_worm: bool = False
    max_ring_teeth: int = 120
    planets_count: int = 3
    strict_ring_inventory: bool = False

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> SolverConfig:
        """Loads configuration from a JSON file, or falls back to system defaults.

        Args:
            config_path: Path to configuration file. If None, checks default locations.
        """
        if config_path is None:
            # Check for config/default_config.json relative to project root or package
            candidate_paths = [
                Path("config/default_config.json"),
                Path(__file__).resolve().parent.parent.parent / "config" / "default_config.json",
            ]
            for p in candidate_paths:
                if p.is_file():
                    config_path = p
                    break

        if config_path is None or not Path(config_path).is_file():
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            min_t = data.get("min_gear_teeth", 11)
            max_t = data.get("max_gear_teeth", 40)
            enabled = data.get("default_enabled_teeth", list(range(min_t, max_t + 1)))

            cm_data = data.get("cost_model", {})
            cost_model = CostModel(
                stage_penalty=cm_data.get("stage_penalty", 50),
                teeth_multiplier=cm_data.get("teeth_multiplier", 1.0),
                worm_gear_multiplier=cm_data.get("worm_gear_multiplier", 3.0),
            )

            pcm_data = data.get("planetary_cost_model", {})
            planetary_cost_model = PlanetaryCostModel(
                ring_multiplier=pcm_data.get("ring_multiplier", 1.5),
                stage_penalty=pcm_data.get("stage_penalty", 60),
                teeth_multiplier=pcm_data.get("teeth_multiplier", 1.0),
            )

            sd_data = data.get("solver_defaults", {})
            return cls(
                min_gear_teeth=min_t,
                max_gear_teeth=max_t,
                default_enabled_teeth=sorted(enabled),
                cost_model=cost_model,
                planetary_cost_model=planetary_cost_model,
                max_solutions=sd_data.get("max_solutions", 3),
                max_stages=sd_data.get("max_stages", 4),
                allow_approximate=sd_data.get("allow_approximate", False),
                use_worm=sd_data.get("use_worm", False),
                max_ring_teeth=data.get("max_ring_teeth", 120),
                planets_count=data.get("planets_count", 3),
                strict_ring_inventory=data.get("strict_ring_inventory", False),
            )
        except Exception:
            return cls()
