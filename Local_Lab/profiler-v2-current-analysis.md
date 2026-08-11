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

## 2026-08-12 R09 transport/setup detail split

Because the largest R09 phase still mixed local loops, MPI, volume
conservation, time averaging, and wet/dry masks, sites 207--212 split those
components without entering any inner grid loop. Diagnostic build job
`118965294` produced
`Local_Lab/builds/profiling/diagnostic_20260811T174038Z_21596/bin/oceanM`,
SHA-256
`255bc63ab5b11f8a6fc06dc7149989271b11899d51182362649a1825af593a1e`.
Summary job `118965815`, run
`Local_Lab/runs/profile128/r09-transport-phases-diagnostic-summary_20260811T174749Z_45008`,
ended normally, passed all diagnostic checks, and remained bitwise identical
for all 26 variables.

| transport/setup detail | Grid 1 mean | Grid 2 mean | Grid 2 share of parent |
| --- | ---: | ---: | ---: |
| mass-flux compute | 0.049 s | 0.154 s | 8.3% |
| mass-flux exchange | 0.106 s | 0.417 s | 22.5% |
| volume conservation | 0.001 s | 0.002 s | 0.1% |
| time averages | 0.041 s | 0.120 s | 6.5% |
| final average exchange | 0.002 s | 0.010 s | 0.5% |
| `wetdry_tile` | 0.362 s | 1.139 s | 61.5% |

The Grid-2 child sum is `1.8419 s` versus the same-run parent site 199 at
`1.8533 s`, a `99.39%` coverage; Grid 1 is `0.5606/0.5629 s`, also `99.58%`.
The added six timers execute 25500 times per rank and raise diagnostic R09
relative to the previous summary, which is observer effect and is not used as
a score comparison. Phase proportions and same-run parent/child coverage are
the valid result. `wetdry_tile`, not the three visible mass-flux loops, is the
next compute kernel to inspect; the mass-flux exchange is a separate MPI
candidate and must not be attributed to stencil arithmetic.

Ordinary score build job `118965267` produced candidate
`Local_Lab/runs/validation/candidate_20260811T174036Z_25028`, SHA-256
`8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`,
again byte-identical to the accepted score binary. The bounded evidence bundle
is
`profile_bundle_logs/r09-transport-phases-diagnostic-summary_20260811T174749Z_profile_bundle.json`.

## 2026-08-12 R09 wetdry final attribution

The apparent `wetdry_tile` hotspot was split into rho-mask construction,
current masks, average accumulation/exchange, final average masks, and full
masks/exchange (sites 213--218). Summary job `118966817`, run
`r09-wetdry-phases-diagnostic-summary_20260811T180536Z_32978`, passed all
checks and remained bitwise identical. On Grid 2, the same-run wetdry parent
was `1.1786 s`; current masks were `0.7236 s`, average-mask exchange was
`0.3479 s`, rho-mask construction was `0.0618 s`, and all remaining phases
together were below `0.035 s`. The child sum covered `99.08%` of the parent.

Because the current-mask routine itself still ended with a four-array halo,
the final sites 219/220 split its compute and exchange. Diagnostic build job
`118967522` produced
`Local_Lab/builds/profiling/diagnostic_20260811T181520Z_21942/bin/oceanM`,
SHA-256
`a3eb7aed1297cdfe60fe037f8c4c28504d1972f73d7ecaf76ff98d09d87c9aaa`.
Summary job `118967950`, run
`Local_Lab/runs/profile128/r09-wetdry-compute-exchange-diagnostic-summary_20260811T182131Z_61245`,
passed normal-end, metadata, parent consistency, and exact comparison.

| current-mask component | Grid 1 mean | Grid 2 mean | Grid 2 share |
| --- | ---: | ---: | ---: |
| mask compute | 0.104 s | 0.208 s | 29.5% |
| four-array exchange | 0.136 s | 0.492 s | 69.8% |

The child sum is `0.7004/0.7057 s` on Grid 2 (`99.25%`) and
`0.2395/0.2408 s` on Grid 1 (`99.48%`). Wetdry is therefore primarily a
communication path in this configuration, not the largest compute kernel.
The R09 compute priority returns to advection/rotation (`1.040 s`), followed
by horizontal viscosity (`0.666 s`); current-mask compute (`0.208 s`) is a
smaller follow-up. Average-mask and current-mask exchanges remain distinct
MPI candidates.

Ordinary score build job `118967479` produced candidate
`Local_Lab/runs/validation/candidate_20260811T181452Z_2084`, SHA-256
`8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`,
byte-identical to the accepted score binary. The bounded final bundle is
`profile_bundle_logs/r09-wetdry-compute-exchange-diagnostic-summary_20260811T182131Z_profile_bundle.json`.

## 2026-08-12 R09 advection/rotation detail split

Sites 221--224 split the existing R09 advection/rotation phase into fourth-order
flux/stencil construction, flux divergence, Coriolis, and curvilinear terms.
Diagnostic build job `118969270` produced
`Local_Lab/builds/profiling/diagnostic_20260811T183530Z_996/bin/oceanM`,
SHA-256
`94b03265a68d36823ba106d491c94ae098b1b77eebb13eb05662af7c7be75a7a`.
Summary job `118969887`, run
`Local_Lab/runs/profile128/r09-advection-phases-diagnostic-summary_20260811T184250Z_16246`,
ended normally, passed all diagnostic checks, and remained bitwise identical
to the accepted score reference for all 26 variables.

| advection/rotation detail | Grid 1 mean | Grid 2 mean | Grid 2 share |
| --- | ---: | ---: | ---: |
| fourth-order flux/stencil construction | 0.227 s | 0.635 s | 60.7% |
| flux divergence | 0.035 s | 0.098 s | 9.4% |
| Coriolis | 0.050 s | 0.148 s | 14.2% |
| curvilinear term | 0.059 s | 0.164 s | 15.7% |

The child sum covers `0.3696/0.3714 s` on Grid 1 (`99.52%`) and
`1.0455/1.0533 s` on Grid 2 (`99.26%`). Every child executes 5124 times per
rank on Grid 1 and 25200 times per rank on Grid 2, matching the parent. The
fourth-order flux/stencil loops are therefore the next R09 compute target;
divergence, Coriolis, curvilinear work, viscosity, and wetdry MPI must remain
outside the first model experiment.

The official ifort 2017 no-IPO report for the actual preprocessed
`step2d.f90` shows that the major inner `i` loops in this phase already
vectorize with vector length 2, generally through unaligned/multiversioned
paths. The first hypothesis should consequently target scratch-plane memory
traffic or loop structure while preserving the fourth-order stencil,
coefficients, expression order, and exact output; merely adding SIMD
directives is not supported by the evidence.

Ordinary score build job `118969277` produced candidate
`Local_Lab/runs/validation/candidate_20260811T183604Z_27828`, SHA-256
`8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`,
again byte-identical to the accepted score binary. The bounded evidence bundle
is
`profile_bundle_logs/r09-advection-phases-diagnostic-summary_20260811T184250Z_profile_bundle.json`.

## 2026-08-12 accepted R09 re-ranking after Dgrad staging

After accepting commit `818523e`, diagnostic build job `118973376` produced
`Local_Lab/builds/profiling/diagnostic_20260811T192833Z_25307/bin/oceanM`,
SHA-256
`7e5594ce4ec25898aa3ccc350c947a2530acf7febc6064ca3865af473aebe693`.
Summary job `118973783`, run
`Local_Lab/runs/profile128/r09-post-dgrad-diagnostic-summary_20260811T193436Z_10681`,
ended normally, passed diagnostic validation, and remained bitwise identical
to the accepted score run for all 26 variables.

| accepted R09 compute phase | Grid 1 mean | Grid 2 mean |
| --- | ---: | ---: |
| horizontal viscosity | 0.255 s | 0.666 s |
| fourth-order flux/stencil construction | 0.222 s | 0.615 s |
| momentum update | 0.175 s | 0.443 s |
| curvilinear term | 0.059 s | 0.163 s |
| Coriolis | 0.050 s | 0.150 s |
| flux divergence | 0.035 s | 0.098 s |

Sites 221--224 cover `1.0272/1.0349 s` on Grid 2 (`99.26%`) and
`0.3663/0.3681 s` on Grid 1 (`99.51%`), with unchanged calls. Diagnostic
walls are not compared to score or used to claim the accepted speedup; their
valid use here is the same-run ranking. Horizontal viscosity is now the
largest R09 compute child, narrowly ahead of the remaining flux/stencil work.
The next profiler experiment must therefore split site 203 into its active
stress construction and divergence/update loop families before any viscosity
model rewrite. The bounded bundle is
`profile_bundle_logs/r09-post-dgrad-diagnostic-summary_20260811T193436Z_profile_bundle.json`.

## 2026-08-12 R09 harmonic-viscosity detail split

The active application header defines `UV_VIS2`, not `UV_VIS4`. Sites 225--228
therefore split site 203 into PSI-point total depth, RHO-point stress flux,
PSI-point stress flux, and final divergence/update. Diagnostic build job
`118974394` produced
`Local_Lab/builds/profiling/diagnostic_20260811T194256Z_33436/bin/oceanM`,
SHA-256
`9d7b573482652352ef52efbc2aa6471e9d2d025b98fe4ad904164803bb5b03b2`.
Summary job `118975018`, run
`Local_Lab/runs/profile128/r09-viscosity-phases-diagnostic-summary_20260811T195009Z_46567`,
passed normal end, exact comparison, metadata, and diagnostic consistency.

| harmonic-viscosity phase | Grid 1 mean | Grid 2 mean | Grid 2 share |
| --- | ---: | ---: | ---: |
| PSI total depth (`Drhs_p`) | 0.018 s | 0.053 s | 7.9% |
| RHO stress flux | 0.054 s | 0.145 s | 21.5% |
| PSI stress flux | 0.126 s | 0.321 s | 47.6% |
| divergence/update | 0.057 s | 0.146 s | 21.7% |

All four sites execute 5124 times per rank on Grid 1 and 25200 times on Grid
2. Their sum covers `0.2550/0.2567 s` on Grid 1 (`99.35%`) and
`0.6659/0.6735 s` on Grid 2 (`98.88%`). PSI stress construction is the first
specific loop target. Source-lifetime review should test whether its
`Drhs_p` input has a single producer and consumer under the active UV_VIS2
branch; if so, fusing those loops can remove a scratch-plane round trip while
preserving every point expression. RHO stress and divergence must remain out
of that first model experiment.

Ordinary score build job `118974398` produced
`Local_Lab/runs/validation/candidate_20260811T194310Z_10750/bin/oceanM`,
SHA-256
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`,
byte-identical to the accepted score binary. The bounded bundle is
`profile_bundle_logs/r09-viscosity-phases-diagnostic-summary_20260811T195009Z_profile_bundle.json`.

## 2026-08-12 R19 GLS phase split

After the supported R09 exact optimization and three rejected PSI-stress
hypotheses, the accepted score bundle was reranked globally. Grid-2 R19 GLS
vertical mixing was the first remaining wide compute region at `5.072 s`;
R34 was only `0.986 s`. Sites 229--238 therefore split only R19 into predictor
horizontal/vertical/BC-exchange and corrector setup-shear, horizontal/vertical
advection, production-dissipation, implicit solve, coefficient construction,
and BC-exchange.

Diagnostic build job `118978051` produced
`Local_Lab/builds/profiling/diagnostic_20260811T203755Z_19135/bin/oceanM`,
SHA-256
`dd341750e053fe5f28dffc748d18d57419647744c6ef671060ba2e09591ad681`.
The parallel ordinary score build job `118978054` produced
`Local_Lab/runs/validation/candidate_20260811T203806Z_15364/bin/oceanM` with
the unchanged accepted SHA-256
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`,
confirming that the new calls compile out of ordinary score binaries.

Summary job `118978391`, run
`Local_Lab/runs/profile128/r19-phases-diagnostic-summary_20260811T204510Z_9860`,
ended normally with all 26 variables bitwise identical. The first report
exposed a profiler acceptance omission: sites 229--238 were parsed but were
not yet required and `gls_vertical_mixing` was not mapped to parent R19.
Commit `e7ace00` adds both checks and a regression test. Reprocessing the same
rank logs, without rerunning the model, passes all metadata/site checks and
gives `1.956883/1.959396 s` coverage on Grid 1 (`99.87%`) and
`5.166464/5.175357 s` on Grid 2 (`99.83%`).

| GLS phase | Grid 1 mean | Grid 2 mean | Grid 2 share of R19 |
| --- | ---: | ---: | ---: |
| predictor horizontal | 0.076 s | 0.197 s | 3.8% |
| predictor vertical | 0.055 s | 0.107 s | 2.1% |
| predictor BC/exchange | 0.133 s | 0.479 s | 9.3% |
| corrector setup/shear | 0.062 s | 0.170 s | 3.3% |
| corrector horizontal advection | 0.083 s | 0.199 s | 3.8% |
| corrector vertical advection | 0.037 s | 0.105 s | 2.0% |
| corrector production/dissipation | 0.543 s | 1.351 s | 26.1% |
| corrector implicit solve | 0.073 s | 0.180 s | 3.5% |
| corrector coefficient construction | 0.766 s | 1.907 s | 36.8% |
| corrector BC/exchange | 0.129 s | 0.471 s | 9.1% |

The next compute target is the corrector coefficient-construction loop family,
not the two communication-heavy BC/exchange phases. Before changing the model,
obtain an ifort vectorization report for the actual preprocessed coefficient
loop and audit the active `Lmy25` path for remaining repeated powers, square
roots, divisions, and invariant GLS constants. Production/dissipation remains
the second target and must not be mixed into that experiment. The bounded
bundle is
`profile_bundle_logs/r19-phases-diagnostic-summary_20260811T204510Z_profile_bundle.json`.

## 2026-08-12 R15 CoSiNE biology broad split

After the R19 coefficient and production hypotheses were rejected, the
accepted score bundle was reranked again. Grid-2 R15 biology was the next
wide compute region at about `3.406 s`, ahead of R27 tracer biharmonic mixing
at `2.251 s` and R34 `step3d_uv` at `0.986 s`. With only sites 239--240 left
in the existing diagnostic capacity, the first R15 pass deliberately uses a
broad two-part split: local setup/light/biogeochemical reactions (site 239),
then sinking, bounds, and final tracer writeback (site 240).

Diagnostic build job `118981479` produced
`Local_Lab/builds/profiling/diagnostic_20260811T215307Z_63581/bin/oceanM`,
SHA-256
`f667e8db7291d2a886d841a6f37474b13c85616e6b9619206bed29aa4ee7584e`.
The parallel ordinary score build job `118981463` produced
`Local_Lab/runs/validation/candidate_20260811T215301Z_13189/bin/oceanM` with
the unchanged accepted SHA-256
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`.

Summary job `118981786`, run
`Local_Lab/runs/profile128/r15-biology-phases-diagnostic-summary_20260811T215947Z_63313`,
ended normally, passed all diagnostic checks, and remained bitwise identical
for all 26 compared variables.

| R15 biology phase | Grid 1 mean | Grid 2 mean | Grid 2 share of R15 |
| --- | ---: | ---: | ---: |
| local setup/light/reactions | 0.800 s | 2.689 s | 78.7% |
| sinking/bounds/final writeback | 0.235 s | 0.724 s | 21.2% |

The two sites cover `1.0352/1.0368 s` on Grid 1 (`99.85%`) and
`3.4129/3.4191 s` on Grid 2 (`99.82%`). Grid 1 has 11 ranks with no wet rows,
so the site records correctly have zero calls there while all 64 rank records
remain present. The next profiler change should refine only site 239 into
state/setup, light attenuation, and the main local source/sink equations.
Sinking is not the first compute target. The bounded bundle is
`profile_bundle_logs/r15-biology-phases-diagnostic-summary_20260811T215947Z_profile_bundle.json`.

## 2026-08-12 R15 local-reaction detail

Sites 241--243 refine only site 239 into setup/state extraction, light
attenuation, and the source/sink-equation block. Diagnostic build job
`118982291` produced
`Local_Lab/builds/profiling/diagnostic_20260811T220858Z_61580/bin/oceanM`,
SHA-256
`f7cde25dae474173f7e3162bf2a5c5fbf8bfbc1a90b82184ab9174c9dfd05f54`.
Ordinary score build job `118982300` again produced the accepted SHA-256
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`.

Summary job `118982658`, run
`Local_Lab/runs/profile128/r15-local-reactions-diagnostic-summary_20260811T221600Z_39597`,
passed normal end, exact comparison, rank/node metadata, and all diagnostic
checks.

| local-reaction phase | Grid 1 mean | Grid 2 mean | Grid 2 share of R15 |
| --- | ---: | ---: | ---: |
| setup/state extraction | 0.141 s | 0.417 s | 12.1% |
| light attenuation | 0.080 s | 0.252 s | 7.3% |
| source/sink equations and gas exchange | 0.584 s | 2.039 s | 59.1% |

The three children cover site 239 by `99.93%` on Grid 1 and `99.90%` on
Grid 2. The source/sink block is the first target, but it combines one large
pointwise `k/i` reaction loop with subsequent O2/CO2 gas-exchange calls. The
last profiler split should separate those at their loop/call boundary; it
must not put timers inside the innermost grid-point loop. The bounded bundle
is
`profile_bundle_logs/r15-local-reactions-diagnostic-summary_20260811T221600Z_profile_bundle.json`.

## 2026-08-12 R15 source/sink final split

Sites 244--245 split site 243 at the existing loop/call boundary into the
pointwise CoSiNE reaction loop and the subsequent O2/CO2 gas-exchange work.
Diagnostic build job `118983033` produced
`Local_Lab/builds/profiling/diagnostic_20260811T222214Z_39310/bin/oceanM`,
SHA-256
`cd847c95584850ecc5e9393df4675cc1232ad32c1969f3e8416a0b123882d268`.
Ordinary score build job `118983020` again produced the unchanged accepted
SHA-256
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`.

Summary job `118983545`, run
`Local_Lab/runs/profile128/r15-source-sink-diagnostic-summary_20260811T222901Z_57614`,
passed normal end, exact comparison, and all diagnostic checks.

| source/sink child | Grid 1 mean | Grid 2 mean | Grid 2 share of R15 |
| --- | ---: | ---: | ---: |
| pointwise CoSiNE reactions | 0.352 s | 1.094 s | 31.7% |
| O2/CO2 gas exchange | 0.234 s | 0.951 s | 27.6% |

The two children cover site 243 by `99.91%` on both grids. The pointwise
reaction loop is the first compute target, but only narrowly. Obtain an ifort
vectorization report from the actual preprocessed source before choosing one
exact-equivalence repeated-computation or memory hypothesis. Gas exchange is
a stable guard and must not be modified in the same model experiment. The
bounded bundle is
`profile_bundle_logs/r15-source-sink-diagnostic-summary_20260811T222901Z_profile_bundle.json`.

The accepted preprocessed `biology.f90` was then compiled separately under
the production Intel 2017 toolchain. Compile-only job `118983818` reports that
the pointwise inner `i` loop is already vectorized at vector length 2, with
estimated speedup 1.27, five serialized `exp` calls, 25 divides, and many
unaligned unit-stride loads/stores. The report is preserved at
`/tmp/r15-biology-pointwise.optrpt` in the local analysis environment.

The first exact model hypothesis removed two `k>1` branches whose two bodies
were expression-wise identical. Build job `118983953` produced a distinct
binary, but the single score job `118984274`, run
`Local_Lab/runs/profile128/r15-redundant-k-branches-4n64-16ppn_20260811T224705Z_55569`,
rejected it: all 26 comparisons were exact, while Grid-2 R15 regressed 0.61%,
Grid-1 R15 did not improve, and Grid-2 R09 regressed 2.31%. The 0.54% lower
raw total coincided with favorable R03/R44 movement and is not attributable
to the source. The candidate was not committed or rerun; its record is in
`/tmp/r15-redundant-k-branches-failed/`.

A second exact pointwise hypothesis cached five tracer values in scalars and
reused them through the grazing/remineralization block while preserving every
arithmetic association. Build job `118984782` produced a distinct binary, but
score job `118985082`, run
`Local_Lab/runs/profile128/r15-tracer-scalar-cache-4n64-16ppn_20260811T230245Z_9095`,
rejected it. All 26 comparisons were exact; Grid-2 R15 regressed 0.77%,
Grid-2 R09/R35 regressed 3.41%/0.80%, and total regressed 0.45%. Grid-1 R15
improved only 0.26%. The larger scalar live set likely increased register
pressure. The candidate was restored without commit or rerun; evidence is in
`/tmp/r15-tracer-scalar-cache-failed/`.

After two pointwise exact failures, the next R15 target is the nearly equal
gas-exchange child (`0.951 s` on Grid 2). Inspect the actual inlined CO2/O2
solver loops and their compiler report before selecting one hypothesis; do
not continue mechanical scalar caching in the pointwise loop.

The first exact gas-exchange hypothesis hoisted four carbonate residual
invariants from each `ta_iter_1` evaluation to once per safeguarded Newton
solve. Build job `118985412` produced a distinct binary, but score job
`118985734`, run
`Local_Lab/runs/profile128/r15-co2-root-invariants-4n64-16ppn_20260811T231720Z_42607`,
rejected it. All 26 comparisons remained exact; Grid-2/Grid-1 R15 regressed
0.82%/0.30%, total regressed 0.79%, and multiple stable compute regions were
also slower. The candidate was restored without commit or rerun; evidence is
in `/tmp/r15-co2-root-invariants-failed/`.

R15 now has complete three-level attribution and three distinct rejected
exact hypotheses. Stop local micro-tuning without new evidence. The next wide
compute region is Grid-2 R27 biharmonic tracer mixing (about `2.251 s` in the
accepted score bundle); profile its active stencil and boundary phases before
any model rewrite.

## 2026-08-12 R27 biharmonic tracer-mixing phases

The application header defines both `MIX_GEO_TS` and `MIX_S_TS`, but
`t3dmix.F` tests `MIX_S_TS` first. Therefore the active R27 implementation is
`t3dmix4_s.h`, not `t3dmix4_geo.h`; this also explains why the two earlier
coefficient-cache optimizations changed R27.

Diagnostic commit `e329fea` added sites 246--248 at loop-nest boundaries for
the tracer-independent coefficient cache, first harmonic/Laplacian pass, and
second harmonic plus update. Ordinary build job `118986324` reproduced the
accepted score SHA-256 exactly
(`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`), so
the sites are absent from score binaries. Diagnostic build job `118986330`
produced SHA-256
`940b8b7296ed0b604cbb2cca1a672bee476a732747f35d27448cab2aa0394db7`.

Summary job `118986594`, run
`Local_Lab/runs/profile128/r27-t3dmix4-phases-diagnostic-summary_20260811T233659Z_13316`,
ended normally with all 26 comparisons exact and diagnostic validation PASS.
On Grid 2, R27 was `2.2829 s`; coefficient cache, first harmonic, and second
harmonic/update were `0.0612/1.3787/0.8205 s`, together covering `99.02%` of
the parent. The first harmonic alone is about `60.4%` of R27 and is the next
target. Grid 1 showed the same ordering (`0.0247/0.5407/0.3005 s`, `99.42%`
coverage). The high 173400 calls/rank for each harmonic child are expected
from tracer-level boundaries and make this a diagnostic-only attribution;
its wall is not compared with score performance. Evidence bundle:
`profile_bundle_logs/r27-t3dmix4-phases-diagnostic-summary_20260811T233659Z_profile_bundle.json`.
