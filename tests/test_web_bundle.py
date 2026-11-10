"""Tests for Phase 2 web application bundle integrity, packaging, and execution bridge."""

import json
from pathlib import Path
import sys
import zipfile
import pytest

from scripts.build_web_assets import build_web_package


class TestWebBundle:
    """Verifies web application structure, assets, and Python worker execution bridge."""

    def test_build_web_package_creates_valid_zip(self, tmp_path: Path) -> None:
        """Verifies packaging script creates a valid zip containing all gear_reduction modules."""
        out_zip = tmp_path / "gear_reduction.zip"
        build_web_package(output_zip=out_zip)
        assert out_zip.is_file()
        assert out_zip.stat().st_size > 5000  # At least > 5 KB

        with zipfile.ZipFile(out_zip, "r") as zf:
            namelist = zf.namelist()
            assert "gear_reduction/__init__.py" in namelist
            assert "gear_reduction/cli.py" in namelist
            assert "gear_reduction/config.py" in namelist
            assert "gear_reduction/core/models.py" in namelist
            assert "gear_reduction/core/solver.py" in namelist
            assert "gear_reduction/core/planetary.py" in namelist
            assert "gear_reduction/core/planetary_solver.py" in namelist

    def test_web_static_assets_exist(self) -> None:
        """Verifies all required static assets exist in the web/ directory."""
        web_dir = Path(__file__).resolve().parent.parent / "web"
        assert (web_dir / "index.html").is_file()
        assert (web_dir / "css" / "style.css").is_file()
        assert (web_dir / "js" / "app.js").is_file()
        assert (web_dir / "js" / "worker.js").is_file()
        assert (web_dir / "python" / "gear_reduction.zip").is_file()

    def test_github_pages_workflow_configured(self) -> None:
        """Verifies GitHub Actions workflow deploys the web/ folder."""
        workflow_file = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-pages.yml"
        assert workflow_file.is_file()
        content = workflow_file.read_text(encoding="utf-8")
        assert 'path: "web"' in content or "path: 'web'" in content or "path: web" in content

    def test_worker_python_bridge_spur(self) -> None:
        """Simulates worker solve_spur_bridge function directly in Python runtime."""
        from gear_reduction.core.models import CostModel
        from gear_reduction.core.solver import ReductionSolver, parse_ratio

        params = {
            "ratio": "10:1",
            "available_teeth": list(range(11, 41)),
            "use_worm": False,
            "allow_approximate": False,
            "max_solutions": 3,
            "max_stages": 4,
            "worm_multiplier": 3.0,
        }
        target_frac = parse_ratio(params["ratio"])
        cost_model = CostModel(worm_gear_multiplier=params["worm_multiplier"])
        solver = ReductionSolver(
            available_teeth=params["available_teeth"],
            cost_model=cost_model,
            max_stages=params["max_stages"],
        )
        solutions = solver.solve(
            target_ratio=target_frac,
            use_worm=params["use_worm"],
            allow_approximate=params["allow_approximate"],
            max_solutions=params["max_solutions"],
        )
        json_output = json.dumps([s.to_dict() for s in solutions])
        data = json.loads(json_output)
        assert len(data) == 3
        assert data[0]["achieved_ratio"] == 10.0

    def test_worker_python_bridge_planetary(self) -> None:
        """Simulates worker solve_planetary_bridge function directly in Python runtime."""
        from gear_reduction.core.planetary import PlanetaryCostModel
        from gear_reduction.core.planetary_solver import PlanetarySolver
        from gear_reduction.core.solver import parse_ratio

        params = {
            "ratio": "4:1",
            "available_teeth": list(range(11, 41)),
            "stator": "any",
            "allow_approximate": False,
            "max_solutions": 3,
            "max_stages": 3,
            "ring_multiplier": 1.5,
            "max_ring_teeth": 120,
            "planets_count": 3,
            "strict_ring_inventory": False,
        }
        target_frac = parse_ratio(params["ratio"])
        cost_model = PlanetaryCostModel(ring_multiplier=params["ring_multiplier"])
        solver = PlanetarySolver(
            available_teeth=params["available_teeth"],
            cost_model=cost_model,
            max_stages=params["max_stages"],
            max_ring_teeth=params["max_ring_teeth"],
            planets_count=params["planets_count"],
            strict_ring_inventory=params["strict_ring_inventory"],
        )
        solutions = solver.solve(
            target_ratio=target_frac,
            stator=params["stator"],
            allow_approximate=params["allow_approximate"],
            max_solutions=params["max_solutions"],
        )
        json_output = json.dumps([s.to_dict() for s in solutions])
        data = json.loads(json_output)
        assert len(data) > 0
        assert data[0]["type"] == "planetary"
        assert data[0]["achieved_ratio"] == 4.0
