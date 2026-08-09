# Cache predictor C4 tracer transport half-planes

## Hypothesis

- Accepted commit: `182673a` (`perf(tracer): skip predictor masks on all-wet
  faces`).
- Reference run: `Local_Lab/runs/profile128/predictor-all-wet-horizontal-mask-4n64-16ppn_20260809T035110Z_60524`.
- The active C4 predictor recomputes `Huon*0.5` and `Hvom*0.5` for every one
  of 15 tracers at a fixed level.  Cache those exact first products in two
  tile-local planes once per level, matching the already accepted corrector
  implementation.  The remaining expression, loop order, masks and values are
  unchanged.
- Target: lower Grid-1/2 R22 with unchanged calls and no offsetting regression
  in R09, R19, R35, R39, R44, R49, R54 or R55.
- Reject on abnormal completion, missing output, any nonzero comparison, an
  unchanged binary hash, or no causal R22 improvement.

## Result

- Build job `118811482`; candidate
  `candidate_20260809T041208Z_22653`; binary SHA-256
  `f571ff75f9200663ea07e9d966c5dc455cd7364f57de3898f25291aff8ab757c`.
  The hash differs from the accepted binary, confirming the active path.
- 4n64 DEMO job `118811614`; run
  `cache-predictor-c4-transport-halves-4n64-16ppn_20260809T041907Z_20538`.
  It ended normally and all 26 variables were bitwise identical.
- R22 calls were unchanged.  Grid 1 R22 fell `2.459875 -> 2.449193 s`
  (`-0.43%`); Grid 2 fell `7.100594 -> 7.007780 s` (`-1.31%`).
  Profile total rose `70.18 -> 70.80 s`, while unrelated R35, R39, R49 and
  R55 all slowed together.  R22 improved against that allocation-wide
  headwind, which is stronger causal evidence than the noisy total.
- **Accepted.**  Evidence bundle:
  `profile_bundle_logs/cache-predictor-c4-transport-halves-4n64-16ppn_20260809T041907Z_profile_bundle.json`.
