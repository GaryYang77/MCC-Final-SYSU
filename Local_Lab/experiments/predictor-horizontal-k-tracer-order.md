# Reorder predictor horizontal tracer advection by vertical level

- Accepted anchor: `1cb989fa1093cf88cf2a700fd562e9765335fe47`.
- Reference run:
  `Local_Lab/runs/profile128/tracer-horizontal-k-order-4n64-16ppn_20260808T130839Z_46165`
  (job `118786248`, 4n64/16ppn, 8x8, 60/300; profile total `79.75 s`,
  all 26 comparisons bitwise zero).
- Target: Grid-1/2 R22 (`3d_equations_predictor`), whose reference wall is
  `2.886/8.285 s` with `61/300` calls per rank.

## Falsifiable hypothesis

The predictor's horizontal tracer-advection block in `pre_step3d.F` has the
same independent tracer/vertical-level structure as the corrector block just
accepted in `step3d_t.F`, but it still traverses all vertical transport planes
once per tracer. Interchanging only the independent `itrc` and `k` loops keeps
one `Huon`/`Hvom` level and its metric/mask planes hot while processing the
tracers for that level.

Every output element retains its original arithmetic and is written once;
there is no cross-tracer or cross-level recurrence in this block. Point-source
handling remains inside the same `(k,itrc)` pair. Equations, precision, input,
MPI, boundary processing, and profiling are unchanged.

Expected numerical behavior is bitwise identical. Expected performance is
lower R22 on both grids, unchanged calls and rank balance, and lower or neutral
total wall. Any nonzero comparison, abnormal end, or no useful R22 direction
falsifies the hypothesis.

## Result

- Clean PROFILE build: job `118787296`, candidate
  `Local_Lab/runs/validation/candidate_20260808T135010Z_20174`; build report
  passed and binary SHA-256 was
  `55f5db49967fa9b18615907230b06458c11d6d0971806aa1f773a07aa659e620`.
- 4n64 score DEMO: job `118787413`, run
  `Local_Lab/runs/profile128/predictor-horizontal-k-order-4n64-16ppn_20260808T135659Z_14464`.
  It ended normally and passed output/comparison checks; all 26 variables had
  `RMSE=0` and `max_abs=0`.
- This was a broadly slow allocation: total changed from `79.75` to `93.01 s`.
  Non-target Grid-2 compute regions R09/R19/R35/R39 were respectively
  `13.7/19.8/34.8/31.0%` slower than the reference, whereas target R22 was only
  `5.6%` slower (`8.285` to `8.748 s`). Grid 1 showed the same separation:
  R09/R19/R35 were `23.9/16.4/29.1%` slower, versus only `2.7%` for R22
  (`2.886` to `2.966 s`). Calls were unchanged.

Decision: accept with explicit allocation-noise uncertainty. The target
outperformed the surrounding compute slowdown by roughly `8-29` percentage
points on both grids, the equivalent corrector transformation is already
accepted, and this candidate changes neither arithmetic nor output bits. The
run becomes the next output/reference anchor, but its absolute wall is not a
new estimate of steady-state performance.

Bundle:
`profile_bundle_logs/predictor-horizontal-k-order-4n64-16ppn_20260808T135659Z_profile_bundle.json`.
