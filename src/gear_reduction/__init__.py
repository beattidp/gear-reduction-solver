"""Gear Reduction Solver package.

A modular toolkit to compute optimal multi-stage gear trains based on user-defined
reduction ratios, available gear sets, worm drive constraints, and cost models.
"""

from .core.models import CostModel, GearPair, GearTrain, ReductionSolution
from .core.solver import ReductionSolver

__all__ = [
    "GearPair",
    "GearTrain",
    "ReductionSolution",
    "CostModel",
    "ReductionSolver",
]

__version__ = "0.1.0"
