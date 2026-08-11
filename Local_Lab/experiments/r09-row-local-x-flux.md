# R09 row-local X-flux experiment

## Pre-declared hypothesis

- Accepted start commit: `08dbe65cd616d05c35b8e3f6adaf7a797a191e3a`.
- Branch: `perf/r09-row-local-x-flux`.
- Correctness channel: exact-equivalence.
- Target: Grid-2 R09 site 221, fourth-order barotropic momentum
  flux/stencil construction. Job `118969887` measured `0.634544 s`, 60.7% of
  the R09 advection/rotation child sum; the four child sites cover 99.26% of
  site 202.
- Hottest loop family: the four fourth-order `UFx/UFe/VFx/VFe` constructions
  and their preceding `grad/Dgrad` stencils in
  `ROMS/Nonlinear/step2d_LF_AM3.h`. The first experiment changes only the
  `Dgrad` staging immediately before `UFe` and `VFx`: `UFe` consumes one
  `Dgrad` row, while `VFx` consumes the current and preceding rows.
- Access/vectorization: Fortran `i` is the continuous inner dimension. The
  official Intel 2017 no-IPO report for the actual preprocessed source shows
  the major inner loops vectorized with vector length 2, usually through
  unaligned/multiversioned paths. The hypothesis is cache locality, not
  missing SIMD.
- Proposed change: batch `Dgrad` construction and flux consumption by row.
  `UFe` consumes its newly produced row immediately; `VFx` initializes the
  first required row once, then produces the next row immediately before its
  consumer. This shortens the reuse distance of `Dgrad` without changing any
  point expression, stencil coefficient, physical-edge fallback, loop bounds,
  or produced flux plane.
- Expected result: site 221 and normally R09/total wall decrease; call counts
  and all non-target regions remain stable. The benefit may be small because
  tile scratch planes can already fit in cache; a non-improving result falsifies
  the hypothesis and is rejected after the single DEMO.
- Floating-point/order risk: operations for each array element remain textually
  identical, and there is no cross-row data dependency. Only independent row
  execution order changes. Exact 26-variable output is required; any nonzero
  result rejects the candidate rather than switching channels after the fact.
- Register-pressure risk: unchanged inside each vector loop. The compiler sees
  the same inner loop bodies; no loops are fused at the `i` level.
- Excluded work: `grad` staging, `UFx/VFe`, divergence, Coriolis,
  curvilinear terms, viscosity, wetdry, MPI, compiler flags, and profiler
  definitions.

## Gate results

- Local tests: `python -m pytest -q Local_Lab/tests` passed all 71 tests;
  `git diff --check` passed.
- Clean PROFILE build job `118970910` passed. Candidate directory:
  `Local_Lab/runs/validation/candidate_20260811T185602Z_24311`; binary SHA-256:
  `1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`.
- The post-change inner loop bodies are textually identical to those covered by
  the Intel 2017 no-IPO report: the major `i` loops remain vector-length-2
  vector loops. Only their surrounding outer-`j` execution order changed, so
  this candidate does not add a new SIMD or register-pressure mechanism.
- The single 4n64/16ppn 60/300 score DEMO was job `118971429`, retained at
  `Local_Lab/runs/profile128/r09-row-local-dgrad-4n64-16ppn_20260811T190232Z_3600`.
  It ended normally and all 26 variables had `RMSE=0` and `max_abs=0` against
  accepted reference
  `r22-vertical-time-metric-4n64-16ppn_20260811T164844Z_21545`.
- Grid-2 R09 min/mean/max changed from
  `5.370619/5.448426/5.641630 s` to
  `5.280076/5.346913/5.564065 s`; the mean improvement is `0.101514 s`
  (`1.86%`) and is consistent across ranks. Grid-1 R09 also improved from
  `1.816738` to `1.791012 s` (`1.42%`). Calls were unchanged.
- Raw total improved from `68.191513` to `67.695250 s` (`0.73%`). This run also
  received favorable volatile R03/R44 changes totaling more than the raw total
  delta, so the full `0.73%` must not be attributed to the source. Stable
  guards were small/mixed: Grid-2 R19 `+0.53%`, R22 `-0.03%`, R35 `+0.42%`,
  and R54 `-0.02%`. The rank-consistent target-region improvement is the
  acceptance evidence.
- Decision: accept this exact candidate as the next daily score reference.
  Its credible cumulative total improvement remains far below the 5% full-run
  trigger, so no no-profile or complete three-day run is allowed.
