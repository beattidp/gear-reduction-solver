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

    known_gear_teeth: list[int] = field(
        default_factory=lambda: list(range(9, 41))
    )
    available_gear_teeth: list[int] = field(
        default_factory=lambda: list(range(9, 41))
    )
    min_gear_teeth: int = 9
    max_gear_teeth: int = 40
    default_enabled_teeth: list[int] = field(
        default_factory=lambda: list(range(9, 41))
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

    def add_known_gear(self, teeth: int, enable: bool = True) -> None:
        """Adds a gear size to the known catalog and optionally enables it."""
        if teeth <= 0:
            raise ValueError(f"Gear teeth count must be positive, got {teeth}")
        if teeth not in self.known_gear_teeth:
            self.known_gear_teeth = sorted(self.known_gear_teeth + [teeth])
        if enable and teeth not in self.available_gear_teeth:
            self.available_gear_teeth = sorted(self.available_gear_teeth + [teeth])
        self.default_enabled_teeth = list(self.available_gear_teeth)
        self.min_gear_teeth = min(self.known_gear_teeth)
        self.max_gear_teeth = max(self.known_gear_teeth)

    def remove_known_gear(self, teeth: int) -> None:
        """Removes a gear size from the known catalog and available set."""
        if teeth in self.known_gear_teeth:
            self.known_gear_teeth = [t for t in self.known_gear_teeth if t != teeth]
        if teeth in self.available_gear_teeth:
            self.available_gear_teeth = [t for t in self.available_gear_teeth if t != teeth]
        self.default_enabled_teeth = list(self.available_gear_teeth)
        if self.known_gear_teeth:
            self.min_gear_teeth = min(self.known_gear_teeth)
            self.max_gear_teeth = max(self.known_gear_teeth)

    def set_gear_availability(self, teeth: int, available: bool) -> None:
        """Sets whether a known gear is available in the calculation inventory."""
        if teeth not in self.known_gear_teeth:
            raise ValueError(f"Gear {teeth}T is not in known gears catalog.")
        if available and teeth not in self.available_gear_teeth:
            self.available_gear_teeth = sorted(self.available_gear_teeth + [teeth])
        elif not available and teeth in self.available_gear_teeth:
            self.available_gear_teeth = [t for t in self.available_gear_teeth if t != teeth]
        self.default_enabled_teeth = list(self.available_gear_teeth)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the configuration to a dictionary compatible with JSON schema."""
        return {
            "known_gear_teeth": list(self.known_gear_teeth),
            "available_gear_teeth": list(self.available_gear_teeth),
            "min_gear_teeth": self.min_gear_teeth,
            "max_gear_teeth": self.max_gear_teeth,
            "default_enabled_teeth": list(self.available_gear_teeth),
            "cost_model": {
                "stage_penalty": self.cost_model.stage_penalty,
                "teeth_multiplier": self.cost_model.teeth_multiplier,
                "worm_gear_multiplier": self.cost_model.worm_gear_multiplier,
            },
            "planetary_cost_model": {
                "ring_multiplier": self.planetary_cost_model.ring_multiplier,
                "stage_penalty": self.planetary_cost_model.stage_penalty,
                "teeth_multiplier": self.planetary_cost_model.teeth_multiplier,
            },
            "max_ring_teeth": self.max_ring_teeth,
            "planets_count": self.planets_count,
            "strict_ring_inventory": self.strict_ring_inventory,
            "solver_defaults": {
                "max_solutions": self.max_solutions,
                "max_stages": self.max_stages,
                "allow_approximate": self.allow_approximate,
                "use_worm": self.use_worm,
            },
        }

    def save(self, config_path: str | Path) -> None:
        """Saves current configuration to a JSON file."""
        target = Path(config_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")

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

            min_t = data.get("min_gear_teeth", 9)
            max_t = data.get("max_gear_teeth", 40)

            # Determine known gears
            if "known_gear_teeth" in data and isinstance(data["known_gear_teeth"], list):
                known_teeth = sorted(list(set(int(t) for t in data["known_gear_teeth"])))
            elif "default_enabled_teeth" in data and isinstance(data["default_enabled_teeth"], list):
                known_teeth = sorted(list(set(int(t) for t in data["default_enabled_teeth"])))
            else:
                known_teeth = list(range(min_t, max_t + 1))

            # Determine available gears
            if "available_gear_teeth" in data and isinstance(data["available_gear_teeth"], list):
                available_teeth = sorted(list(set(int(t) for t in data["available_gear_teeth"])))
            elif "default_enabled_teeth" in data and isinstance(data["default_enabled_teeth"], list):
                available_teeth = sorted(list(set(int(t) for t in data["default_enabled_teeth"])))
            else:
                available_teeth = list(known_teeth)

            if known_teeth:
                min_t = min(known_teeth)
                max_t = max(known_teeth)

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
                known_gear_teeth=known_teeth,
                available_gear_teeth=available_teeth,
                min_gear_teeth=min_t,
                max_gear_teeth=max_t,
                default_enabled_teeth=available_teeth,
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
