# Worklog: Mechanical Refinements & Solver Optimizations

**Date**: 2026-11-10  
**Time**: 08:44:00-07:00  
**Agent**: Antigravity  
**User**: beattidp  

---

## Summary of Actions
1. **Resolved 11T / Dummy Stage Issue (`31:1 --worm`)**:
   - Enforced strict inequality $P < G$ for reduction spur stages, eliminating $1:1$ dummy stages ($11T \to 11T$) that provide zero reduction while adding friction, cost, and backlash.
   - Refined exact solver stage deepening: when exact solutions exist at minimal achievable depth $k_{\min}$, the solver returns immediately rather than expanding to deeper stages that artificially cancel teeth or add 1.88× cost penalties.
   - Verified `31:1 --worm` now returns exactly the 1 true optimal solution: `[Worm(1T) -> 31T]`.
2. **Implemented Worm Wheel Cost Multiplier (`60:1 --worm`)**:
   - Added `worm_gear_multiplier: float = 3.0` (configurable) in `CostModel`, `SolverConfig`, `default_config.json`, and CLI flag `--worm-multiplier`.
   - Formula: $\text{Cost} = \sum_{\text{spur}} (P_i + G_i) + \sum_{\text{worm}} (P_{\text{worm}} + \text{round}(M_{\text{worm}} \times G_{\text{worm}})) + (\text{stage\_penalty} \times k)$.
   - Verified that for `60:1 --worm`, solutions now prioritize compact worm wheels: 20T worm wheel ranks #1 (Cost: 205, Rel. Cost: 1.0000), followed by 18T (Cost: 207) and 22T (Cost: 208), while the expensive 30T worm wheel is deprioritized (Cost: 224).
3. **Implemented Multiset Parts Deduplication & Progressive Torque Ordering (`10:1`)**:
   - Added `canonical_parts_key()` to identify the multiset bill-of-materials required by a solution.
   - Added `progression_penalty()` to evaluate mechanical torque progression ($P_1 \le P_2 \dots$ and $G_1 \le G_2 \dots$).
   - Deduplicated solutions using identical physical parts: for `10:1`, `[11T -> 40T] [12T -> 33T]` was recognized as an inverted permutation of `[11T -> 33T] [12T -> 40T]` and eliminated.
   - The top 3 solutions for `10:1` now each feature a genuinely distinct set of physical gears: `{11, 12, 33, 40}`, `{12, 12, 36, 40}`, and `{12, 13, 39, 40}`.
4. **Automated Verification**:
   - Ran complete pytest suite with 33 unit tests: 100% pass rate in 7.08s.
   - Verified CLI output across all test cases.
5. **Git Commit**:
   - Committed changes with clean message per project guidelines.
