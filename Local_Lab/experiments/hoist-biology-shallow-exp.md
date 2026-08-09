# Hoist the biology shallow-water exponential out of the depth loop

## Hypothesis

- Accepted commit: `94e1bab` (`perf(tracer): reuse predictor passive
  diffusion coefficients`).
- Reference run: `Local_Lab/runs/profile128/cache-predictor-passive-vdiff-coef-4n64-16ppn_20260809T043805Z_5981`.
- The Feng Zhou shallow-water light factor depends on
  `z_w(i,j,1)` only, but its clamp and `EXP(cff2)` are currently recomputed at
  every one of 34 vertical levels.  Determine shallow/deep status and evaluate
  the exponential once per column.  The existing per-level
  `float(k)/float(N)*factor` expression and all light, biology and update loops
  retain their order.
- Deep columns continue to avoid the exponential entirely.  Physics, inputs,
  precision, masks, MPI and profiler are unchanged.
- Target: lower Grid-1/2 R15 with unchanged calls and bitwise-identical output;
  guard R09, R19, R22, R35, R39, R44, R49, R54 and R55.
- Reject on abnormal completion, missing output, any nonzero comparison, or no
  causal R15 improvement.

## Result

- Build job `118812737`; candidate `candidate_20260809T045013Z_12109`;
  binary SHA-256
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- 4n64 DEMO job `118812932`; run
  `hoist-biology-shallow-exp-4n64-16ppn_20260809T045708Z_48473`.
  It ended normally and all 26 variables were bitwise identical.
- R15 calls were unchanged.  Grid 1 R15 fell `1.055723 -> 1.051346 s`
  (`-0.41%`); Grid 2 fell `3.416310 -> 3.410297 s` (`-0.18%`).  Other compute
  regions moved in mixed directions and show no causal regression.  The small
  gain indicates limited shallow-column coverage and/or compiler loop
  invariant motion, but the two-grid target direction matches the removed
  redundant exponentials.
- **Accepted under the team's relaxed logically-effective rule.**  Evidence
  bundle:
  `profile_bundle_logs/hoist-biology-shallow-exp-4n64-16ppn_20260809T045708Z_profile_bundle.json`.
