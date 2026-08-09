# Skip redundant final tracer masking on all-wet tiles

- Accepted anchor: `7a7f561753484471d7fb28c19746bebd1f3b49d5`.
- Reference run:
  `Local_Lab/runs/profile128/gls-kkl-boundary-powers-4n64-16ppn_20260809T005828Z_6875`
  (job `118807778`, 4n64/16ppn, 8x8, 60/300; profile total `71.70 s`,
  all 26 comparisons bitwise zero).
- Target: Grid-1/2 R35, specifically profiler-v2 final/update site 135.
- Guard regions: R09, R19, R22, R39, R44, R49, R54 and R55.

## Falsifiable hypothesis

At the end of `step3d_t`, the static land/sea mask is applied over the full
tracer volume separately for every tracer.  Grid 2 is fully wet, so these
passes repeatedly multiply each value by exactly one.  Mixed Grid-1 tiles
also repeat the same mask inspection for every tracer and level.

Scan the tile's static `rmask` once per call.  If every relevant point is
exactly one, skip the redundant volume multiplications; otherwise retain the
existing loops unchanged.  The scan is outside the tracer and vertical loops,
and the fallback retains the exact expression, bounds and traversal order.
No model equation, time step, precision, MPI path, input, profiling source or
wet/dry mask update is changed.

Expected output is bitwise identical.  Expected performance evidence is a
lower profiler-v2 final/update subphase and lower R35 on fully wet Grid 2,
with unchanged call counts and neutral compute guards.  A build failure, any
nonzero comparison, or no useful Grid-2 target direction rejects the
experiment.  Because mask control flow changes, an otherwise accepted DEMO
must also pass the independent 1-rank validation gate before commit.

## Result

Accepted.

- Clean PROFILE build: job `118808098`, candidate
  `Local_Lab/runs/validation/candidate_20260809T011743Z_1464`; binary
  SHA-256
  `73b7e9672080c9cfb03508a8732f8d12e64f6062bfcc4680bf3e68f90f252404`.
- 4n64 score DEMO: job `118808175`, run
  `Local_Lab/runs/profile128/tracer-all-wet-final-mask-4n64-16ppn_20260809T012419Z_39605`.
  It ended normally with complete output/profile reports, and all 26
  comparisons had `RMSE=0` and `max_abs=0`.
- The intended fully wet Grid-2 target improved: R35 mean changed from
  `9.0539` to `8.8480 s` (`-2.27%`, about `0.206 s`) with unchanged calls.
  Mixed-mask Grid 1 retained the original volume loop and paid for the extra
  scan: R35 changed from `3.2043` to `3.2301 s` (`+0.80%`, about `0.026 s`).
  The net target-region direction is therefore clearly positive.
- Profile total changed from `71.70` to `72.58 s`.  This does not contradict
  the compute result: volatile Grid-2 R44 increased `32.10%` and R03 increased
  `34.96%`; model compute guards were stable apart from small allocation
  variation.  The target improvement and exact output justify acceptance
  under the documented noise policy.
- Because mask control flow changed, independent 1-rank validation job
  `118808210` was run.  Candidate
  `Local_Lab/runs/validation/candidate_20260809T012824Z_21354` passed all 13
  variables; its `144.711 s` wall is compatibility evidence only.
- Evidence bundle:
  `profile_bundle_logs/tracer-all-wet-final-mask-4n64-16ppn_20260809T012419Z_profile_bundle.json`.
