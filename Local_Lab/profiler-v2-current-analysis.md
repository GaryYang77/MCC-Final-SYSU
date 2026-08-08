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
