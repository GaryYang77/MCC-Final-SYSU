# Cache predictor passive-tracer vertical-diffusion coefficients

## Hypothesis

- Accepted commit: `6e085fc` (`perf(tracer): cache predictor C4 transport
  halves`).
- Reference run: `Local_Lab/runs/profile128/cache-predictor-c4-transport-halves-4n64-16ppn_20260809T041907Z_20538`.
- In the explicit predictor vertical-diffusion block, `ltrc=MIN(NAT,itrc)`.
  Salinity and all ecological tracers therefore use the same `Akt(...,NAT)`
  and repeat the identical depth reciprocal and coefficient products.  Cache
  the exact left-associated coefficient in the no-longer-live `CF(i,k)` work
  array once per row, then reuse it for every `ltrc==NAT` tracer.  Temperature
  retains the original loop and expression.
- The tracer difference and final multiplication remain in their original
  order.  Equations, precision, masks, MPI, inputs and profiler are unchanged.
- Target: lower Grid-1/2 R22 with unchanged calls and bitwise-identical output;
  guard R09, R19, R35, R39, R44, R49, R54 and R55.
- Reject on abnormal completion, missing output, any nonzero comparison, or no
  causal R22 improvement.

## Result

- Build job `118811990`; candidate `candidate_20260809T043130Z_7224`;
  binary SHA-256
  `be8cc209b833853c943c8f5f7a75b351e3e4c76cf5fbf1bf8dd89e1c8ae1eede`.
- 4n64 DEMO job `118812238`; run
  `cache-predictor-passive-vdiff-coef-4n64-16ppn_20260809T043805Z_5981`.
  It ended normally and all 26 variables were bitwise identical.
- R22 calls were unchanged.  Grid 1 R22 fell `2.449193 -> 2.399885 s`
  (`-2.01%`); Grid 2 fell `7.007780 -> 6.863495 s` (`-2.06%`).
  Profile total was effectively flat (`70.80 -> 70.87 s`) because unrelated
  R44 waiting rose by `1.10/0.49 s` on Grid 1/2; the matching two-grid R22
  reduction is causal.
- **Accepted.**  Evidence bundle:
  `profile_bundle_logs/cache-predictor-passive-vdiff-coef-4n64-16ppn_20260809T043805Z_profile_bundle.json`.
