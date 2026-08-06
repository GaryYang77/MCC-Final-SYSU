# Reuse vertical-diffusion factorization across tracers

- Accepted anchor: `46a59a7cc45fb02ff6eafa88c6500fe693668d95`
- Reference: `route-fcross-to-receivers-4n64-16ppn_20260805T145632Z_51111`
- Target: Grid 2 region 35 (`9.895260 s` in the accepted DEMO and
  `424.636 s` in the complete three-day profile).
- Hypothesis: the implicit vertical-diffusion matrix depends on `Hz`, `Akt`,
  `z_r`, `dt`, and `ltrc`, but not on the tracer right-hand side. The current
  code rebuilds and refactors it for every tracer. Since
  `ltrc=MIN(NAT,itrc)`, all biological tracers consecutively reuse the second
  active-tracer diffusivity and therefore share exactly the same matrix.
- Cache the off-diagonal coefficients, diagonal, inverse pivots, and eliminated
  upper diagonal for the current `ltrc`. Each tracer still executes the same
  forward and backward substitutions on its own right-hand side.
- The physical scheme, matrix coefficients, pivot expressions, and RHS
  arithmetic order are unchanged. Only repeated coefficient construction and
  factorization are removed.
- Expected numerical behavior: bitwise-identical output, materially lower
  region 35 and total wall, unchanged MPI call counts.
- Falsifier: any comparison difference or a clear region-35/total regression.

## Result

- Build job: `118657881`
- Profile candidate: `candidate_20260806T025627Z_15899`
- Profile binary SHA-256:
  `41bd3c090a1039529804c660408450b3ae0f30cdd42c7a64c5db99dec09fad27`
- Profile job: `118658023`
- Run: `reuse-tracer-vdiff-factorization-4n64-16ppn_20260806T030317Z_26389`
- Parallel correctness: PASS; normal end, complete outputs, and all 26
  comparisons have `RMSE == 0` and `max_abs == 0`.
- Total profile mean: `80.282807 -> 80.029315 s` (`-0.32%`).
- Grid 1 region 35: `3.388554 -> 3.119822 s` (`-7.93%`).
- Grid 2 region 35: `9.895260 -> 9.324338 s` (`-5.77%`).
- Triggered validate job: `118658153`.
- Validate candidate: `candidate_20260806T030737Z_12144`.
- Independent 1-rank validation: PASS; all 26 metrics have `RMSE == 0` and
  `max_abs == 0`; candidate wall `164.879 s` versus sealed baseline
  `188.695 s` (`-12.62%`).

Accepted. Both grids show a targeted region-35 reduction, independent 1-rank
timing confirms the computation saving, all numerical results are bitwise
identical, and total DEMO wall has no regression.
