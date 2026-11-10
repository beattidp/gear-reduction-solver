# Epicyclic / Planetary Gear Configuration Solver

Add an epicyclic (planetary) gear train solver as an alternative solver to the Gear Reduction Solver. The planetary solver models single-stage and cascaded planetary arrangements across all three canonical stator configurations:
1. **Outer Ring is the Stator (fixed)**: Input = Sun, Output = Carrier $\rightarrow$ High-ratio speed reduction ($\text{Ratio} = 1 + R/S > 2$, same direction).
2. **Planet Carrier / Pins is the Stator (fixed)**: Input = Sun, Output = Ring $\rightarrow$ Moderate-ratio speed reduction with inverted rotation ($\text{Ratio} = R/S > 1$, reverse direction).
3. **Sun Gear is the Stator (fixed)**: Input = Ring, Output = Carrier $\rightarrow$ Low-ratio speed reduction ($1 < \text{Ratio} = 1 + S/R < 2$, same direction).

---

## User Review Required

> [!IMPORTANT]
> **Ring Gear Tooth Sourcing Strategy**:
> In standard kit inventories (e.g. 11–40T spur gears), the internal ring gear $R = S + 2P$ naturally exceeds the pinion/planet size ($R \ge 33\text{T}$, up to $120\text{T}$).
> - By default, the solver will allow $S$ and $P$ to be drawn from `available_teeth` (default 11–40T), while $R = S + 2P$ is constrained by a maximum ring size (`max_ring_teeth`, default 120T).
> - If `--strict-ring-inventory` is passed, $R$ will be strictly restricted to `available_teeth`.
> 
> Please review if this meets your intended design expectations.

> [!NOTE]
> **CLI Flag Ergonomics**:
> We propose introducing `--type {spur,planetary,all}` and convenience shorthand flags `--planetary` (`-p`) and `--stator {ring,carrier,sun,any}`.
> When `--planetary` is invoked, the output table clearly identifies the stator, input, and output members alongside tooth counts and ratios.

---

## Open Questions

> [!TIP]
> **Planet Gear Multiplier in Fabrication Cost**:
> For a planetary stage with $N$ planets (default $N=3$):
> $$\text{Cost} = S + (N \times P) + \text{round}(M_{\text{ring}} \times R) + \text{stage\_penalty}_{\text{planetary}}$$
> We propose setting $M_{\text{ring}} = 1.5$ (accounting for the higher fabrication difficulty of internal tooth rings) and $\text{stage\_penalty}_{\text{planetary}} = 60$ (accounting for carrier machining and precision pin alignment). We will expose `--ring-multiplier` in CLI/config.

---

## Kinematic & Geometric Mechanics

For a simple planetary stage with Sun ($S$), Planet ($P$), Ring ($R$), and Carrier with $N$ planets ($N=3$):

1. **Coaxiality Constraint**:
   $$R = S + 2P \iff P = \frac{R - S}{2}$$
   Requires $R > S$ and $(R - S)$ to be an even integer.

2. **Equally Spaced Meshing / Assembly Condition**:
   For $N$ planets distributed at equal $360^\circ / N$ angles:
   $$(S + R) \pmod N == 0$$

3. **Adjacent Planet Tip Clearance**:
   To prevent adjacent planet gear teeth from colliding on their orbit radius $r = (S + P)/2$:
   $$(S + P) \sin\left(\frac{\pi}{N}\right) > P + 2$$

4. **Speed Reduction Stator Modes** ($\text{Ratio} > 1.0$):
   - **Ring Stator**: $\text{Ratio} = 1 + \frac{R}{S} = \frac{S + R}{S}$ (Forward rotation)
   - **Carrier Stator**: $\text{Ratio} = \frac{R}{S}$ (Inverted rotation)
   - **Sun Stator**: $\text{Ratio} = 1 + \frac{S}{R} = \frac{S + R}{R}$ (Forward rotation)

---

## Proposed Changes

### Core Domain Models

#### [NEW] [planetary.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/planetary.py)
- `PlanetaryStator` enum: `RING`, `CARRIER`, `SUN`.
- `PlanetaryStage`:
  - Fields: `sun: int`, `planet: int`, `ring: int`, `stator: PlanetaryStator`, `planets_count: int = 3`.
  - Properties: `ratio: Fraction`, `is_inverted: bool`, `input_element: str`, `output_element: str`.
  - Geometric checks: $R = S + 2P$, $(S + R) \pmod N == 0$, planet tip clearance.
  - Serialization: `to_dict()`.
- `PlanetaryCostModel`:
  - Attributes: `ring_multiplier: float = 1.5`, `stage_penalty: int = 60`, `teeth_multiplier: float = 1.0`.
  - Method: `compute_cost(stages: Sequence[PlanetaryStage]) -> int`.
- `PlanetarySolution`:
  - Encapsulates single-stage or cascaded multi-stage planetary trains.
  - Fields: `stages: tuple[PlanetaryStage, ...]`, `achieved_ratio: Fraction`, `cost: int`, `relative_cost: float`, `is_approximate: bool`, `deviation_percentage: str | None`.

---

### Planetary Solver Algorithm

#### [NEW] [planetary_solver.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/planetary_solver.py)
- `PlanetarySolver`:
  - Precomputes all valid single-stage `(S, P, R, Stator)` configurations meeting assembly, coaxiality, and clearance constraints.
  - Implements Meet-in-the-Middle and branch-and-bound graph traversal for multi-stage planetary cascades (e.g. Stage 1 carrier output driving Stage 2 sun input).
  - Supports `--stator {ring, carrier, sun, any}` filtering.
  - Supports exact search with immediate minimal-stage termination, and bounded approximate search if `--approx` is enabled.
  - Multi-solution ranking by `relative_cost` and torque progression.

---

### Package Exports & Configuration

#### [MODIFY] [__init__.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/core/__init__.py)
- Export `PlanetaryStator`, `PlanetaryStage`, `PlanetarySolution`, `PlanetaryCostModel`, `PlanetarySolver`.

#### [MODIFY] [config.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/config.py) & [default_config.json](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/config/default_config.json)
- Add planetary configuration parameters: `max_ring_teeth: int = 120`, `planets_count: int = 3`, `ring_gear_multiplier: float = 1.5`, `planetary_stage_penalty: int = 60`.

---

### CLI Interface

#### [MODIFY] [cli.py](file:///home/beattidp/Documents/antigravity/gear-reduction-solver/src/gear_reduction/cli.py)
- Add arguments:
  - `--planetary` (`-p`): Enable planetary solver mode.
  - `--type {spur,planetary,all}`: Solver family selection.
  - `--stator {ring,carrier,sun,any}`: Filter planetary solutions by stationary member.
  - `--planets`: Number of planet gears (default 3).
  - `--ring-multiplier`: Multiplier for internal ring gear tooth cost.
  - `--max-ring-teeth`: Upper bound for ring gear tooth count.
- Update table formatter and JSON output to display planetary stage configuration (`[Ring Stator: S=12T, P=12T, R=36T]`).

---

## Verification Plan

### Automated Tests
Run pytest with full coverage:
```bash
PYTHONPATH=src pytest -v tests/test_planetary.py
PYTHONPATH=src pytest -v tests/
```

Test cases to implement in `tests/test_planetary.py`:
1. **Geometric Invariants & Clearances**:
   - Verify rejection of invalid sets violating $R = S + 2P$.
   - Verify rejection when $(S + R) \pmod N \ne 0$.
   - Verify planet tip clearance calculation.
2. **Exact Kinematics for All 3 Stators**:
   - Ring fixed: $1 + R/S$ (e.g. $S=12, P=12, R=36 \implies \text{Ratio} = 4:1$).
   - Carrier fixed: $R/S$ with `is_inverted=True` (e.g. $S=12, P=12, R=36 \implies \text{Ratio} = 3:1$ reverse).
   - Sun fixed: $1 + S/R$ (e.g. $S=12, P=12, R=36 \implies \text{Ratio} = 48/36 = 4/3 = 1.3333$).
3. **Multi-Stage Planetary Cascades**:
   - Target ratios like 16:1 or 20:1 using 2-stage planetary combinations.
4. **CLI Integration**:
   - `python3 -m gear_reduction.cli -r 4:1 --planetary`
   - `python3 -m gear_reduction.cli -r 3:1 --planetary --stator carrier`
   - `python3 -m gear_reduction.cli -r 4:3 --planetary --stator sun`
   - JSON output verification.

### Manual Verification
- Test CLI directly with various target ratios (e.g., 4:1, 10:1, 60:1) and compare spur vs. planetary outputs.
