# Cache tracer horizontal update metric

- Accepted anchor: `89e8af1e319a318fc4e0634c603df99175229980`.
- Reference run:
  `Local_Lab/runs/profile128/stack-arrays-step2d-prestep3d-4n64-16ppn_20260808T142714Z_24979`
  (job `118787917`, 4n64/16ppn, 8x8, 60/300; profile total
  `77.95 s`, all 26 comparisons bitwise zero).
- Target: Grid-1/2 R35, especially profiler-v2 horizontal tracer advection
  site 132 (`2.316/6.361 s` in the accepted low-noise trace).
- Guard regions: R09, R19, R22, R39, R49, R54 and R55.

## Falsifiable hypothesis

The final horizontal-advection update in `step3d_t.F` recomputes
`dt(ng)*pm(i,j)*pn(i,j)` for every vertical level and tracer, although all
three inputs are invariant across both loops. The active configuration has 34
levels and multiple physical/biological tracers, so the same two
multiplications and metric loads are repeated hundreds of times per cell and
time step.

Compute the expression once per horizontal cell into a two-dimensional work
plane before the `(k,itrc)` loops, then load that cached value in the existing
update loop. The cached expression preserves the original left-to-right
floating-point operation order. Flux construction, divergence addition,
state update order, bounds, equations, precision, MPI, inputs, profiling and
validation are unchanged. The MPDATA bounds are retained even though the
competition configuration uses C4 horizontal advection.

Expected numerical behavior is bitwise-identical output. Expected performance
is lower Grid-1/2 R35 with unchanged calls and neutral guard regions. Build
failure, any nonzero comparison, or no useful R35 direction falsifies the
hypothesis.

## Result

Accepted.

- Clean PROFILE build: job `118792391`, candidate
  `Local_Lab/runs/validation/candidate_20260808T170755Z_18168`; binary
  SHA-256
  `5a857c894ad86dd6c6638643143e013ebf402296a952c4bf104b30bdcc26161f`.
- 4n64 score DEMO: job `118792838`, run
  `Local_Lab/runs/profile128/cache-tracer-horizontal-metric-4n64-16ppn_20260808T171455Z_24574`.
- Correctness: normal end, complete output/profile, and all 26 comparisons
  had `RMSE=0` and `max_abs=0`.
- Profile total changed from `77.95` to `76.23 s` (`-2.2%`). R44 was much
  faster in this allocation, so the full total difference is not attributed
  to this source change.
- Target R35 improved with unchanged calls on both grids: Grid 1
  `3.2808 -> 3.2477 s` (`-1.01%`) and Grid 2 `9.3171 -> 9.2570 s`
  (`-0.65%`). R09/R19/R22 and the nesting guard regions had no consistent
  offsetting compute regression.

The bundle is
`profile_bundle_logs/cache-tracer-horizontal-metric-4n64-16ppn_20260808T171455Z_profile_bundle.json`.
