# Profiler-v2 current-main analysis

Date: 2026-08-08

## Fresh score DEMO

- Commit: `64cec19`.
- Build job: `118784927`; candidate:
  `Local_Lab/runs/validation/candidate_20260808T121309Z_8318`.
- Binary SHA-256:
  `a7c0fd61ce1d85b0d69ee478c267e3b6d27502e1bf992ce30ff6551492a752dd`.
  This equals the Phase-D score binary hash, proving that the final
  `PROFILE_DIAGNOSTIC` fixes compile out of score mode.
- DEMO job: `118785072`; run:
  `Local_Lab/runs/profile128/profiler-v2-current-score-4n64-16ppn_20260808T122050Z_36051`.
- Configuration: 4 nodes, 64 ranks, 16 ppn, 8x8 tiles, 60/300 steps.
- Profile total: Grid 1 `80.607 s`, Grid 2 `80.605 s`; Slurm elapsed `86 s`.
- Normal end; all 26 variables had `RMSE=0` and `max_abs=0`.

The accepted bundle is
`profile_bundle_logs/profiler-v2-current-score-4n64-16ppn_20260808T122050Z_profile_bundle.json`.

## Why this single run is slower than 75--77 seconds

The binary is byte-identical to the score binary measured at `75.13`, `76.40`,
and `77.25 s` during Phase-D. The current `80.61 s` is therefore not a source
or profiler regression.

Against the low-noise Phase-D trace allocation, the current total increased by
about `7.7%`, while the main compute/nesting regions were nearly unchanged:

| Region | Trace run | Current score | Change |
| --- | ---: | ---: | ---: |
| Grid-2 R35 tracer corrector | 9.298 s | 9.316 s | +0.2% |
| Grid-2 R39 nesting | 9.224 s | 9.241 s | +0.2% |
| Grid-2 R54 put receiver data | 4.043 s | 4.037 s | -0.2% |
| Grid-2 R19 GLS | 6.531 s | 6.457 s | -1.1% |
| Grid-1 R44 broadcasts | 3.184 s | 7.186 s | +125.7% |
| Grid-2 R44 broadcasts | 1.275 s | 2.711 s | +112.6% |
| Grid-1 R03 input/read distribution | 0.682 s | 1.999 s | +192.9% |

Call counts were identical. R03/R44 account for essentially all of the excess
wall, indicating allocation/filesystem/arrival-time noise rather than slower
model kernels. This is why a one-run daily workflow must inspect the target
region and noise regions as well as total wall.

## What profiler-v2 adds to the next optimization decision

The low-noise accepted trace decomposes Grid-2 R35 (`9.298 s`) as:

| Corrector phase | Mean wall |
| --- | ---: |
| horizontal tracer advection | 6.361 s |
| final/update work | 1.436 s |
| vertical advection | 0.929 s |
| vertical diffusion | 0.540 s |
| setup/halo/inverse thickness | 0.026 s |

Grid-1 shows the same ordering. Horizontal tracer advection is therefore the
first compute hypothesis. It should be investigated with the Intel vectorizer
report and loop/data-access evidence before rewriting arithmetic.

Grid-2 `put_refine3d` accounts for `3.953 s` of the `4.043 s` R54 total. It is
the second strong compute hypothesis; instrumenting interpolation subphases or
hoisting demonstrably invariant weights is more promising than another broad
nesting change.

For routed assembly:

- Grid-1 contact3d: total `0.145 s`, MPI `0.119 s`, unpack `0.016 s`, pack
  `0.009 s`, plan `<0.001 s`.
- Grid-2 f2csum: total `0.080 s`, pack `0.059 s`, MPI `0.017 s`, unpack
  `0.002 s`, plan `<0.001 s`.

Route-plan reconstruction is not a worthwhile target. These two operations
also explain only small fractions of parent R49 (`3.258 s` on Grid 1 and
`3.339 s` on Grid 2). Before another R49 rewrite, extend the diagnostic sites
to cover the remaining assemble modes; otherwise a change would still be
guided by an inclusive total rather than the responsible path.

R41/R42 halo exchanges and R44 broadcasts remain visibly imbalanced, but the
current profiler does not yet provide complete pack/wait/unpack coverage for
them. Add those diagnostic sites only when one becomes the selected hypothesis,
not to every daily score run.

## Efficient acceptance policy

A score-profiler speedup is a strong daily proxy, not proof of no-profile
speedup. A candidate can affect timer-call overhead, compiler layout, caches,
or MPI arrival order differently between builds. The efficient policy is:

1. Run one score DEMO per candidate; require normal end and the 26-variable
   comparison.
2. Require the target region to move as predicted, with stable call counts and
   no offsetting compute regression.
3. Inspect total wall. If it agrees, accept. If it disagrees only because known
   volatile R03/R44 time changed while compute regions support the hypothesis,
   record the uncertainty and let the team accept or reject without an
   automatic rerun.
4. Do not run diagnostic summary/trace for routine acceptance. Use them only
   to select or explain a hypothesis.
5. Confirm accumulated gains with a same-source no-profile build at a phase
   boundary and for the final full run.

This retains nearly all of the proposed throughput improvement without making
the scientifically false claim that score and no-profile speedups are always
identical.

## 2026-08-09 phase-boundary no-profile measurement

After the accepted tracer metric caches and two narrow K-kl unit-power
specializations, current `main` was `07f8d83`. The no-profile build was job
`118798584` at
`Local_Lab/builds/profiling/no_profile_20260808T190838Z_44010`; its binary
SHA-256 is
`d2ed66a500699fb9245339276c10a3867eb614e25adb0c7d55c692a6b8dd7ccb`.

The prescribed same-allocation `off-on` pair was job `118798959`:

- control/no-profile run:
  `Local_Lab/runs/profile128/gls-unit-powers-phase-paired-overhead-off_20260808T191501Z_43554`,
  `75.53 s`;
- score PROFILE run:
  `Local_Lab/runs/profile128/gls-unit-powers-phase-paired-overhead-on_20260808T191501Z_43554`,
  `73.83 s`.

Both runs ended normally and their output comparisons passed. The apparent
`-2.25%` profiler overhead is runtime/order noise, not evidence that
instrumentation accelerates the model. The defensible current no-profile DEMO
measurement is therefore `75.53 s`, down from the prior phase pair's
`78.75 s`. This pair reinforces the workflow distinction: score regions can
establish a causal kernel improvement, but a phase-boundary no-profile run is
still required to state the actual score.

## 2026-08-09 C4 transport phase boundary

After accepting the corrector C4 half-transport cache, `main` was `d68e187`.
The new no-profile build was job `118802582` at
`Local_Lab/builds/profiling/no_profile_20260808T204414Z_52068`; binary SHA-256
was `6a92f9cd82c97fb341108eb4cd83c0b65bdf99529ee1435fd0f220184dbfb40f`.

Same-allocation `off-on` pair job `118802758` passed:

- no-profile/control:
  `Local_Lab/runs/profile128/c4-transport-phase-paired-overhead-off_20260808T205120Z_23679`,
  `75.03 s`;
- score PROFILE:
  `Local_Lab/runs/profile128/c4-transport-phase-paired-overhead-on_20260808T205120Z_23679`,
  `72.44 s`.

The apparent `-3.45%` overhead is again execution-order noise. The actual
current phase score is the `75.03 s` no-profile control, a further `0.50 s`
improvement over the preceding `75.53 s` phase pair.

## 2026-08-09 t3dmix4 phase boundary

After accepting the two `t3dmix4_s` coefficient-cache changes, `main` was
`c76d25c`. The fresh no-profile build was job `118804097` at
`Local_Lab/builds/profiling/no_profile_20260808T215642Z_10570`; its binary
SHA-256 was
`ae33988f6e8560dfcb4e777a092343b3781425fa8357a1845236d8508440efbe`.

Same-allocation `off-on` pair job `118804317` passed:

- no-profile/control:
  `Local_Lab/runs/profile128/t3dmix4-phase-paired-overhead-off_20260808T220627Z_2975`,
  `73.10 s`;
- score PROFILE:
  `Local_Lab/runs/profile128/t3dmix4-phase-paired-overhead-on_20260808T220626Z_2975`,
  `72.87 s`.

Both runs ended normally and their 26-variable comparisons passed. The
observed `-0.31%` difference is within runtime noise. The authoritative
no-profile phase score is therefore `73.10 s`, leaving `3.10 s` to the
`70.0 s` objective. The bounded evidence bundle is
`profile_bundle_logs/t3dmix4-phase-paired-overhead-on_20260808T220626Z_profile_bundle.json`.

## 2026-08-09 all-wet tracer-mask phase boundary

After accepting 4D halo send/unpack overlap, predictor surface-halo batching,
the narrow K-kl boundary-power specialization, and the two all-wet tracer mask
fast paths, current `main` was `0458b06`. The fresh no-profile build was job
`118808994` at
`Local_Lab/builds/profiling/no_profile_20260809T021836Z_20429`; its binary
SHA-256 was
`9ec32991b8844558b606f2a60f42d2c011c6db23edbd43d7b78f61c447b826be`.

Same-allocation `off-on` pair job `118809110` passed:

- no-profile/control:
  `Local_Lab/runs/profile128/all-wet-mask-phase-paired-overhead-off_20260809T022450Z_57287`,
  `71.72 s`;
- score PROFILE:
  `Local_Lab/runs/profile128/all-wet-mask-phase-paired-overhead-on_20260809T022450Z_57287`,
  `70.42 s`.

Both runs ended normally and all 26 comparison variables passed. The apparent
`-1.81%` overhead is execution-order/system noise, not acceleration from
instrumentation. The authoritative no-profile phase score is therefore
`71.72 s`, an improvement of `1.38 s` over the previous `73.10 s` phase
boundary. The `70.0 s` objective is not yet achieved; `1.72 s` remains. The
bounded evidence bundle is
`profile_bundle_logs/all-wet-mask-phase-paired-overhead-on_20260809T022450Z_profile_bundle.json`.

## 2026-08-11 R35 tracer-flux assembly split

The R35 horizontal `assembly` site was split into setup/allocation, pack, MPI,
and unpack sites 188--191. The final diagnostic build was Slurm job
`118955218`, binary
`Local_Lab/builds/profiling/diagnostic_20260811T145213Z_36291/bin/oceanM`,
SHA-256
`04715f1564aaea4911e3a40de70bea44246926a18a5ec16989cff61cd2eaaac0`.
The accepted final summary is job `118955359`, run
`Local_Lab/runs/profile128/r35-tracer-flux-assembly-gridlabel-final-summary_20260811T145818Z_52798`.
It ended normally, remained bitwise identical for all 26 variables, and passed
diagnostic metadata and parent-region consistency checks.

For Grid 2, parent assembly mean was `3.2544 s`; child means were setup
`0.0006 s`, pack `0.4991 s`, MPI `1.9691 s`, and unpack `0.7839 s`. Thus MPI
accounts for about 60.5%, while direct pack/unpack memory work accounts for
about 39.4% (`1.2830 s`). For Grid 1, parent assembly was `1.3238 s`; setup,
pack, MPI, and unpack were `0.0003/0.1170/0.9584/0.2478 s` respectively. The
calls per rank match the parent exactly: 300 on Grid 2 and 61 on Grid 1.

An earlier summary job `118954652` is retained as failed profiler evidence: the
first patch started sites 188/189 in the adjacent boundary-flux routine and
stopped them in the tracer routine. The model and exact output comparison
passed, but diagnostic consistency correctly rejected the nonsensical
cross-call totals. The corrected test now scopes instrumentation assertions to
the `assemble_tracer_fluxes` subroutine. A second summary established the
phase values but exposed donor/receiver grid labels being swapped; the final
diagnostic-only `profile_ng` argument fixes that label without changing the
non-diagnostic call signature.

Ordinary score build job `118955028` produced SHA-256
`ff763073d469f1e36a42cc7cd5b12c14ee28d9cd57e38e3a9fd35bd4fe223632`,
byte-identical to the accepted score binary. The new sites therefore remain
fully excluded from score/no-profile code. Since the entire Grid-2 assembly
is below 5% of the roughly 68-second DEMO, even eliminating it cannot by itself
trigger a full three-day run. Its pack/unpack loops are nevertheless a
measured exact-equivalence compute candidate for accumulation under the new
5% full-run budget rule.

## 2026-08-12 R22 pre_step3d phase split

The next wide compute region, R22 `pre_step3d`, was split into diagnostic sites
192--198: tracer setup, horizontal predictor, vertical advection, vertical
diffusion, U momentum, V momentum, and tracer boundary/exchange. Diagnostic
build job `118958291` produced
`Local_Lab/builds/profiling/diagnostic_20260811T160152Z_46516/bin/oceanM`,
SHA-256
`5e9c4816ba0083624204694d748b32afbab39f43d8cd2063e64299361b13843b`.
Summary job `118958689` is retained at
`Local_Lab/runs/profile128/r22-pre-step3d-phases-diagnostic-summary_20260811T160957Z_867`.
It ended normally, passed diagnostic metadata and parent consistency, and all
26 variables remained bitwise identical to accepted score reference
`tracer-flux-direct-copy-4n64-16ppn_20260811T151359Z_47837`.

| R22 subphase | Grid 1 mean | Grid 2 mean | Grid 2 calls/rank |
| --- | ---: | ---: | ---: |
| tracer setup | 0.155 s | 0.452 s | 300 |
| tracer horizontal predictor | 0.828 s | 2.273 s | 300 |
| tracer vertical advection | 0.515 s | 1.407 s | 300 |
| tracer vertical diffusion | 0.474 s | 1.352 s | 300 |
| U momentum predictor | 0.065 s | 0.184 s | 9187.5 |
| V momentum predictor | 0.054 s | 0.160 s | 9150 |
| tracer boundary/exchange | 0.317 s | 1.029 s | 300 |

The child sum covers `99.96%` of R22 on both grids: Grid 1
`2.4079/2.4088 s`, Grid 2 `6.8554/6.8584 s`. The high U/V site call counts are
expected because those timers are scoped per J row; they do not indicate that
momentum dominates R22. Grid-2 tracer horizontal predictor is the largest
compute-only child and is therefore the next kernel target. It should first be
matched to the actual loop nests and ifort vectorization report. Vertical
advection/diffusion and the mixed boundary/exchange phase remain measured
follow-ups; the latter needs another split before attributing its wall to
compute versus MPI.

Ordinary score build job `118958278` produced candidate
`Local_Lab/runs/validation/candidate_20260811T160157Z_8090`, binary SHA-256
`98be8b4a3c11e548596ac00ab9a6b9b1e2d3ed0270c867919490e8febd67f485`.
It is byte-identical to the current accepted score binary, proving that all new
R22 diagnostic sites compile out of score mode.

## 2026-08-12 first R22 model experiments

The exact C4 direct-flux experiment removed the horizontal intermediate
gradient materialization without algebraic cancellation. Job `118960121`, run
`r22-c4-direct-flux-4n64-16ppn_20260811T163329Z_61411`, was bitwise identical
and reduced Grid-2 R22 by `2.60%`, but raw total rose `0.50%` and unchanged GLS
rose `3.63%`. Because its predeclared total/guard condition was not satisfied,
the source was rejected and restored; the server run remains evidence and the
local record is archived under `/tmp/r22-c4-direct-flux-failed/`.

The next exact experiment reused the already computed `cffpmnp` in the final
vertical-advection update instead of repeating `cff*pm*pn` for every tracer and
level. Commit `952677f`; build job `118961035`, binary SHA-256
`8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`;
score job `118961520`, run
`r22-vertical-time-metric-4n64-16ppn_20260811T164844Z_21545`. All 26 variables
were bitwise identical. Grid-2 R22 fell from `6.853677` to `6.789401 s`
(`-0.94%`), while R09/R19/R35 were stable or improved. Raw total rose `0.62%`,
but on the controlling Grid 1, volatile R03 and R44 increased by `0.339` and
`0.748 s`, exceeding the entire `0.422 s` total regression. The candidate was
therefore accepted without an automatic rerun under the documented noise
exception. It is the next exact score reference, but its cumulative credible
total gain remains far below the 5% full-run trigger.

## 2026-08-12 R09 step2d phase split

R09 `step2d` was split into diagnostic sites 199--206: transport/setup,
free-surface update, pressure gradient, advection/rotation, horizontal
viscosity, forcing/coupling, momentum update, and boundary/exchange.
Diagnostic build job `118963901` produced
`Local_Lab/builds/profiling/diagnostic_20260811T172033Z_12914/bin/oceanM`,
SHA-256
`e38c1652b85d4ce5d3f4ca658576d54b37872e03e3b90dfc905e64164bed5f6b`.
Summary job `118964367` is retained at
`Local_Lab/runs/profile128/r09-step2d-phases-diagnostic-summary_20260811T172740Z_2912`.
It ended normally, passed diagnostic metadata and parent consistency, and all
26 variables remained bitwise identical to accepted score reference
`r22-vertical-time-metric-4n64-16ppn_20260811T164844Z_21545`.

| R09 subphase | Grid 1 mean | Grid 2 mean | Grid 2 calls/rank |
| --- | ---: | ---: | ---: |
| transport/setup | 0.546 s | 1.761 s | 25500 |
| free surface | 0.173 s | 0.573 s | 25200 |
| pressure gradient | 0.114 s | 0.294 s | 25200 |
| advection/rotation | 0.370 s | 1.040 s | 25200 |
| horizontal viscosity | 0.255 s | 0.666 s | 25200 |
| forcing/coupling | 0.021 s | 0.064 s | 25200 |
| momentum update | 0.174 s | 0.442 s | 25200 |
| boundary/exchange | 0.122 s | 0.516 s | 25200 |

The child sum covers `99.74%` of R09 on Grid 1 (`1.7755/1.7802 s`) and
`99.62%` on Grid 2 (`5.3555/5.3757 s`). The extra 300 transport/setup calls
per rank are the intentional `nfast+1` auxiliary calls; the timer is stopped
before that path returns, so all sites remain balanced. Grid-2 transport/setup
is the largest child, followed by advection/rotation and viscosity. The
transport/setup phase contains both local mass-flux preparation and its early
halo/volume-conservation work, so it needs source/vectorization inspection
before deciding whether the next hypothesis is arithmetic, memory, or MPI.
Boundary/exchange is visibly rank-imbalanced and is not treated as a compute
optimization target without a further split.

Ordinary score build job `118963924` produced candidate
`Local_Lab/runs/validation/candidate_20260811T172119Z_3545`, binary SHA-256
`8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`.
It is byte-identical to the accepted score binary, proving that the R09 sites
and enlarged diagnostic-site storage compile out of score mode. The bounded
evidence bundle is
`profile_bundle_logs/r09-step2d-phases-diagnostic-summary_20260811T172740Z_profile_bundle.json`.
