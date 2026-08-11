# R35 horizontal tracer-advection diagnostic split

## Scope and branch contract

- Branch: `profiler/r35-horizontal-subphases`.
- Accepted source before profiler change: `0b4cfc1`.
- This branch changes diagnostic-only sites and their offline definitions.  It
  does not change a model performance hypothesis, arithmetic, loops, inputs,
  score regions, or the no-profile path.
- Target parent: R35 `step3d_t/tracer_corrector`, existing site 132
  `tracer_horizontal_advection`.

## Evidence and hypothesis

The accepted low-noise profiler-v2 trace reports Grid-2 R35 at about `9.298 s`,
of which existing site 132 horizontal advection contributes `6.361 s`.  Site
132 is still too broad to choose a loop transformation safely.

The active `BYE24BIO15` configuration defines `TS_U3ADV_SPLIT`; `globaldefs.h`
therefore selects `TS_C4HADVECTION` in `step3d_t.F`.  The active corrector
horizontal path consists of seven mutually exclusive stages:

| Site | Stage | Placement |
| ---: | --- | --- |
| 181 | metric/mask setup | once per tile/corrector call |
| 182 | C4 half-transport setup | once per vertical level |
| 183 | X-direction differences/gradient/flux | once per level and tracer |
| 184 | Y-direction differences/gradient/flux | once per level and tracer |
| 185 | point sources and nesting boundary extraction | once per level and tracer |
| 186 | flux divergence and tracer update | once per level and tracer |
| 187 | distributed complete-flux assembly | once per tile/corrector call |

The summary run should identify which stage dominates site 132 and show that
the seven-stage mean sum explains nearly all of site 132 without exceeding it.
Only after that result may a model optimization hypothesis be selected.

## Instrumentation constraints

- All new calls are under `PROFILE_DIAGNOSTIC`; score/no-profile preprocessing
  removes them.
- Timers surround loop nests or phases and never execute inside the innermost
  `i` loop.
- Sites 183--186 are intentionally high-frequency and are intended for summary
  mode.  Do not run trace by default; a trace would require a separately sized
  event budget and is unnecessary for choosing the compute loop.
- Existing parent sites 132 and R35 are unchanged.
- Diagnostic validation now requires sites 181--187 and maps operation
  `corrector_horizontal` back to parent R35.

## Acceptance gates

Pending cluster work must prove:

1. local tests and clean diagnostic build pass;
2. summary DEMO ends normally and all 26 exact comparisons pass;
3. sites 181--187 are present on all 64 ranks for both grids with expected
   call-count relationships;
4. their phase sum is positive and no greater than site 132 apart from bounded
   timer resolution;
5. R35 parent consistency and diagnostic metadata validation pass;
6. a fresh score build from the same source is byte-identical to the accepted
   score build or otherwise passes the established profiler isolation check.

No model optimization is accepted on this branch.

## Cluster acceptance result

- Diagnostic clean build: Slurm job `118950150`, build root
  `Local_Lab/builds/profiling/diagnostic_20260811T120154Z_56463`, binary
  SHA-256 `0c47e5c63412d58bff9fb2fbfea8226f6eafa07ec6fd998c52e5838ba771d696`.
- Summary DEMO: Slurm job `118950769`, run
  `Local_Lab/runs/profile128/r35-horizontal-subphases-diagnostic-summary_20260811T120850Z_20363`.
  It completed normally, diagnostic validation passed, and all 26 variables
  passed exact comparison with `RMSE == 0` and `max_abs == 0`.
- All sites 181--187 were active on all 64 ranks for both grids.  Their mean
  sums were `1.9282 s` (Grid 1) and `5.0056 s` (Grid 2), respectively 66.0%
  and 67.0% of R35; both parent-consistency checks passed.
- Grid-2 mean time by subphase was: assembly `3.2049 s`, X flux `0.6273 s`,
  Y flux `0.4646 s`, divergence/update `0.3942 s`, sources/nesting `0.2781 s`,
  transport setup `0.0343 s`, and metric/mask setup `0.0023 s`.
- Assembly is the largest horizontal phase but includes nesting assembly and
  communication.  Among the computation kernels, the X-direction C4 stencil
  is the first hotspot, followed by the Y-direction stencil and divergence
  update.  The next model experiment must therefore start from X-flux compiler
  vectorization evidence, not from an unmeasured rewrite.
- Diagnostic isolation: score clean-build job `118950872`, candidate
  `Local_Lab/runs/validation/candidate_20260811T121259Z_6006`, binary SHA-256
  `ff763073d469f1e36a42cc7cd5b12c14ee28d9cd57e38e3a9fd35bd4fe223632`.
  This is byte-identical to the accepted score binary, proving that the new
  diagnostic sites compile out of the score/no-profile path.

All six acceptance gates above passed.  This profiler branch contains no
model optimization.
