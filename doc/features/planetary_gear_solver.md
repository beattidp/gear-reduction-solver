# Feature Documentation: Epicyclic / Planetary Gear Reduction Solver

## Overview
The Planetary Gear Reduction Solver extends the Gear Reduction Solver domain with epicyclic gear train modeling and multi-stage cascades. It models all three canonical speed reduction stator configurations derived from the fundamental Willis equation:
1. **Ring Fixed (Stator = Outer Ring)**: Input = Sun, Output = Carrier $\rightarrow$ High-ratio speed reduction ($\text{Ratio} = 1 + R/S > 2.0$, forward rotation).
2. **Carrier Fixed (Stator = Carrier Pins)**: Input = Sun, Output = Ring $\rightarrow$ Moderate-ratio speed reduction with inverted output direction ($\text{Ratio} = R/S > 1.0$, reverse rotation).
3. **Sun Fixed (Stator = Sun Gear)**: Input = Ring, Output = Carrier $\rightarrow$ Low-ratio speed reduction ($1.0 < \text{Ratio} = 1 + S/R < 2.0$, forward rotation).

---

## Kinematics & Physical Constraints

### 1. Willis Equation & Velocity Invariants
The angular velocity relation governing an epicyclic stage is:
$$S \omega_S + R \omega_R - (S + R) \omega_C = 0$$

For speed reduction ($\omega_{\text{in}} / \omega_{\text{out}} > 1.0$):
| Stator (Fixed) | Input Member | Output Member | Reduction Ratio Formula | Output Direction | Typical Ratio Range |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ring** ($\omega_R = 0$) | Sun ($\omega_S$) | Carrier ($\omega_C$) | $\frac{S + R}{S} = 1 + \frac{R}{S}$ | Forward | $3:1$ to $10:1$ |
| **Carrier** ($\omega_C = 0$) | Sun ($\omega_S$) | Ring ($\omega_R$) | $\frac{R}{S}$ | **Inverted / Reverse** | $2:1$ to $8:1$ |
| **Sun** ($\omega_S = 0$) | Ring ($\omega_R$) | Carrier ($\omega_C$) | $\frac{S + R}{R} = 1 + \frac{S}{R}$ | Forward | $1.2:1$ to $1.8:1$ |

### 2. Physical & Manufacturing Constraints
Every single-stage planetary set must satisfy:
1. **Coaxiality Constraint**:
   $$R = S + 2P \iff P = \frac{R - S}{2}$$
   Requires $(R - S)$ to be an even integer and $R > S$.
2. **Symmetrical Meshing / Assembly Condition**:
   For $N$ planets symmetrically spaced at $360^\circ / N$:
   $$(S + R) \pmod N == 0 \iff 2(S + P) \pmod N == 0$$
3. **Adjacent Planet Tip Clearance**:
   Planets orbit at radius $r_{\text{orbit}} = (S + P)/2$. The straight-line distance between adjacent planet centers must strictly exceed the planet gear outer diameter ($P + 2$):
   $$(S + P) \sin\left(\frac{\pi}{N}\right) > P + 2$$

---

## Fabrication Cost Model

Fabricating a planetary stage requires 1 sun gear, $N$ identical planet gears, 1 internal ring gear, and precision carrier machining with ground hardened pins and bearings.
$$\text{Cost} = S + (N \times P) + \text{round}(M_{\text{ring}} \times R) + \text{stage\_penalty}_{\text{planetary}}$$
- **Ring Multiplier ($M_{\text{ring}}$)**: Default $1.5\times$, reflecting the higher cost of internal tooth shaping/slotting.
- **Planetary Stage Penalty**: Default $60$, accounting for precision carrier plates and needle roller bearings.

---

## API & Architecture

### Domain Classes (`gear_reduction.core.planetary`)
- `PlanetaryStator`: Enum (`RING`, `CARRIER`, `SUN`).
- `PlanetaryStage`: Immutable dataclass validating coaxiality, assembly, and clearance; calculates exact rational ratio, input/output element, and inversion status.
- `PlanetaryCostModel`: Configurable cost weighting model.
- `PlanetarySolution`: Immutable sequence of planetary stages, exact/approximate ratio, integer cost, relative cost, and torque progression metrics.

### Solver Algorithm (`gear_reduction.core.planetary_solver`)
- `PlanetarySolver`:
  - Pre-enumerates valid single stages meeting all geometric invariants.
  - Implements Meet-in-the-Middle and branch-and-bound graph search for 1 to $k$ stages.
  - Terminates immediately on minimal stage depth for exact solutions.
  - Bounded approximate search when exact ratios are unreachable.
  - Normalizes relative costs to the most cost-effective candidate.

---

## CLI Usage

### Basic Planetary Search
```bash
python3 -m gear_reduction.cli -r 4:1 --planetary
```

### Stator Filtering
```bash
# Force Carrier stator (inverted rotation)
python3 -m gear_reduction.cli -r 3:1 --planetary --stator carrier

# Force Sun stator (low ratio)
python3 -m gear_reduction.cli -r 4:3 --planetary --stator sun
```

### Comparative Spur & Planetary Search
```bash
python3 -m gear_reduction.cli -r 10:1 --type all
```

### Structured JSON Output
```bash
python3 -m gear_reduction.cli -r 10:1 --planetary --json
```

---

## Verification
- Unit test suite: `tests/test_planetary.py` (15 test cases covering geometry, kinematics, multi-stage, approximations, and CLI).
- Total project tests: 48 passed with 0 failures.
