# Reorder horizontal tracer advection by vertical level

- Accepted anchor: `fd73e28fe6c391e49c47a0f076a0fb4967ac5382`.
- Reference run:
  `Local_Lab/runs/profile128/profiler-v2-current-score-4n64-16ppn_20260808T122050Z_36051`
  (job `118785072`, 4n64/16ppn, 8x8, 60/300; profile total `80.61 s`,
  all 26 comparisons bitwise zero).
- Stable same-binary range from Phase-D allocations: `75.13--77.25 s`.
- Target: Grid-1/2 region 35, specifically the horizontal tracer advection
  phase identified by profiler-v2 site 132 (`2.316 s` / `6.361 s` in the
  accepted low-noise trace).

## Falsifiable hypothesis

The Intel 17 no-IPO report retained from job `118740773` shows that the inner
`i` loops in the U3 horizontal advection kernel are already vectorized. The
remaining loop order is tracer outer, vertical level inner, so every tracer
streams the tracer-independent `Huon` and `Hvom` three-dimensional fields from
level 1 through `N` again.

Interchanging only the independent `itrc` and `k` loops keeps one transport
level active while processing all tracers. This should improve cache reuse of
`Huon`, `Hvom`, masks, metrics, and horizontal work arrays without changing
the arithmetic expression or order used for any output element.

Scope is limited to the horizontal advection `T_LOOP/K_LOOP` in
`ROMS/Nonlinear/step3d_t.F`. Equations, precision, bounds, source handling,
nesting flux extraction and assembly, MPI, inputs, profiling, and validation
remain unchanged.

Expected numerical behavior is bitwise-identical output. Expected performance
evidence is lower Grid-1/2 R35 and total score wall with unchanged R35 calls
and no offsetting compute regression. Build failure, any nonzero comparison,
or no useful R35 direction falsifies the hypothesis.

## Result

Accepted.

- Clean score build: job `118786153`, candidate
  `Local_Lab/runs/validation/candidate_20260808T130212Z_25592`, binary SHA-256
  `144aa2ff7a38de593d616f7b605ee430204730d89ed43c4537c310417ec4db9f`.
- 4n64 score DEMO: job `118786248`, run
  `Local_Lab/runs/profile128/tracer-horizontal-k-order-4n64-16ppn_20260808T130839Z_46165`.
- Correctness: normal end, complete outputs/profile, and all 26 comparisons
  have `RMSE=0` and `max_abs=0`.
- Profile total improved `80.607 -> 79.753 s` on Grid 1 and
  `80.605 -> 79.755 s` on Grid 2 (about `-1.06%`).
- Target R35 improved on both grids with unchanged calls: Grid 1
  `3.3815 -> 3.2896 s` (`-2.72%`) and Grid 2 `9.3165 -> 9.2780 s`
  (`-0.41%`).
- R03/R44 remained allocation-sensitive, so not all total movement is
  attributable to the candidate. The consistent target-region direction and
  bitwise output support accepting the cache-local loop order as a small,
  low-risk gain without an automatic repeat.

The accepted bundle is
`profile_bundle_logs/tracer-horizontal-k-order-4n64-16ppn_20260808T130839Z_profile_bundle.json`.
