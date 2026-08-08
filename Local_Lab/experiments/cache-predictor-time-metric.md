# Cache predictor time and horizontal metric coefficients

- Accepted anchor: `89d0a70cd02c1b4c392d32fcf11bb3ebb5d25ce4`.
- Reference run:
  `Local_Lab/runs/profile128/cache-tracer-horizontal-metric-4n64-16ppn_20260808T171455Z_24574`
  (job `118792838`, 4n64/16ppn, 8x8, 60/300; profile total
  `76.23 s`, all 26 comparisons bitwise zero).
- Target: Grid-1/2 R22 (`3d_equations_predictor`), reference
  `2.531/7.326 s` with `61/300` calls per rank.
- Guard regions: R09, R19, R35, R39, R49, R54 and R55.

## Falsifiable hypothesis

For every vertical level and tracer, the predictor horizontal update repeats
the same `iic == ntfirst` branch, constructs the same three time coefficients,
and evaluates the same `cff*pm(i,j)*pn(i,j)` product. The artificial
continuity calculation then rebuilds the same time/metric coefficient for
every vertical level. These values depend only on the current predictor call
and horizontal cell.

Compute the three time coefficients once per call and cache
`cff*pm(i,j)*pn(i,j)` once per horizontal cell. Use those unchanged values in
the existing horizontal state update and artificial-continuity expression.
Each cached product retains the original left-to-right multiplication order;
the two state terms, flux divergence, reciprocal and all update ordering stay
unchanged. Equations, bounds, precision, CPP behavior, MPI, inputs, profiling
and validation are unchanged.

Expected numerical behavior is bitwise-identical output. Expected performance
is lower Grid-1/2 R22 with unchanged calls and neutral guard regions. Build
failure, any nonzero comparison, or no useful R22 direction falsifies the
hypothesis.

## Result

Accepted.

- Clean PROFILE build: job `118793243`, candidate
  `Local_Lab/runs/validation/candidate_20260808T172513Z_8170`; binary SHA-256
  `a14557fba38eb2a04dc771e3d4e23f118478a436a9e689897d57a2855ea7982b`.
- 4n64 score DEMO: job `118793509`, run
  `Local_Lab/runs/profile128/cache-predictor-time-metric-4n64-16ppn_20260808T173126Z_64643`.
- Correctness: normal end, complete output/profile, and all 26 comparisons
  had `RMSE=0` and `max_abs=0`.
- Profile total changed from `76.23` to `74.70 s` (`-2.0%`). The reference
  and candidate have different R44 timing, so the entire total change is not
  attributed to this source optimization.
- Target R22 improved with unchanged calls on both grids: Grid 1
  `2.5310 -> 2.4831 s` (`-1.89%`) and Grid 2 `7.3263 -> 7.2884 s`
  (`-0.52%`). Stable compute and nesting guard regions showed no consistent
  offsetting regression.

The bundle is
`profile_bundle_logs/cache-predictor-time-metric-4n64-16ppn_20260808T173126Z_profile_bundle.json`.
