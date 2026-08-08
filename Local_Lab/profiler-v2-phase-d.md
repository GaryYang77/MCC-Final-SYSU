# Profiler v2 Phase-D evidence

Date: 2026-08-08

## Accepted artifacts

- Source anchor before profiler work: `2195306c`.
- Score PROFILE build: job `118782050`, binary SHA-256
  `a7c0fd61ce1d85b0d69ee478c267e3b6d27502e1bf992ce30ff6551492a752dd`.
- No-profile build: job `118782207`, binary SHA-256
  `5a9e76aa51a580c80c84e4804507a0f3e55aed4ccad2dc3e12b2666fe1d3811f`.
- Final diagnostic build: job `118783692`, binary SHA-256
  `0380e1c536c61d8f1424bedaeedf0cfa99e840bcb0f55b8aab9275a99f0b481d`.
  Its five instrumented Fortran sources passed the build-node aggregate SHA
  check before compilation.

All runs below used 4 nodes, 64 MPI ranks, 16 ranks per node, 8x8 tiles, and
60/300 time steps.

## Score-profiler control

Three same-allocation, alternating-order score/no-profile pairs all ended
normally and compared all 26 variables bitwise (`RMSE=0`, `max_abs=0`):

| Job | Order | Score (s) | No-profile (s) | Difference |
| --- | --- | ---: | ---: | ---: |
| 118782365 | off-on | 76.40 | 81.38 | -6.12% |
| 118782441 | on-off | 75.13 | 75.68 | -0.73% |
| 118782532 | off-on | 77.25 | 75.21 | +2.71% |

Median difference was `-0.73%`. The spread shows allocation noise, but there
is no systematic score-profiler regression. Final competition timing remains
the no-profile binary.

## Summary acceptance

- Job: `118783783` (`off-on`).
- Run:
  `Local_Lab/runs/profile128/profiler-v2-summary-final-on_20260808T111308Z_44067`.
- Diagnostic/no-profile wall: `110.68 / 114.32 s` (`-3.18%`). This is an
  observed perturbation, not a performance score or acceptance threshold.
- Normal end and all 26 variables bitwise identical.
- 64 rank records mapped to four real processor names:
  `j01r2n08` through `j01r2n11`; local ranks were 0--15 per node.
- No events were requested or dropped in summary mode.
- Parent/child consistency passed. Corrector phase sums covered R35 by
  `99.97%` on Grid 1 and `99.96%` on Grid 2. Contact3d and f2csum child phases
  covered their operation totals by `99.65%` and `98.87%`.

The accepted bundle is
`profile_bundle_logs/profiler-v2-summary-final_20260808T111308Z_profile_bundle.json`.

## Trace acceptance

- Job: `118783898` (`on-off`).
- Run:
  `Local_Lab/runs/profile128/profiler-v2-trace-final-on_20260808T111910Z_24934`.
- Diagnostic/no-profile wall: `77.57 / 76.28 s` (`+1.69%`).
- Normal end and all 26 variables bitwise identical.
- Selected ranks `0,16,32,48`, one per node; `148990` events and zero drops.
- Perfetto JSON size `42,861,663` bytes, below the 256 MiB cap. SHA-256:
  `f441633dfb1341e2b090334683872cea913d2a8285e395f07670d0964a78fb79`.
- All profile/diagnostic parent-child consistency checks passed.

The accepted bundle is
`profile_bundle_logs/profiler-v2-trace-final_20260808T111910Z_profile_bundle.json`.
The large Perfetto JSON remains in the remote run directory and is not stored
in Git.

## Evidence for the next optimization stage

On the low-noise trace allocation, Grid-2 R35 was `9.298 s`; its diagnostic
phase sum was `9.293 s` (`99.94%`). On the summary allocation, the phase split
showed horizontal tracer advection as the dominant corrector component:

- Grid 2: horizontal `10.967 s`, update `2.816 s`, vertical advection
  `1.199 s`, vertical diffusion `0.573 s`, setup `0.029 s`.
- Grid 1: horizontal `4.175 s`, update `1.002 s`, vertical advection
  `0.446 s`, vertical diffusion `0.215 s`, setup `0.011 s`.

For the routed nesting paths on the same summary allocation:

- Grid-1 contact3d mean: total `0.216 s`, MPI `0.177 s`, unpack `0.027 s`,
  pack `0.011 s`, plan `<0.001 s`.
- Grid-2 f2csum mean: total `0.120 s`, pack `0.072 s`, MPI `0.044 s`, unpack
  `0.002 s`, plan `<0.001 s`. One rank had a `1.025 s` MPI outlier.
- Grid-2 put_refine3d local interpolation: `6.917 s` mean.

These values show that rebuilding the already cached route plan is not the
current bottleneck. The strongest next code hypotheses are horizontal tracer
advection and `put_refine3d`; contact routing should be investigated through
MPI/rank imbalance or pack/unpack work, not plan construction.

## Phase-D lessons and failed evidence

- Fortran formatted output may insert spaces after `=`; the parser now accepts
  those records.
- Shell `HOSTNAME` identifies the launch environment, not necessarily the MPI
  rank's node. The profiler uses `MPI_Get_processor_name`.
- `MPI_ERROR` conflicts with Fortran's case-insensitive `mpi_error`; the local
  variable is named `diag_ierr`.
- Shared-filesystem views can lag between login and build nodes. The diagnostic
  build compares an aggregate hash of all five instrumented sources before
  compiling.
- An early R35 timer started outside a `j` loop and stopped inside it. Its
  inflated phase time was rejected and the final implementation starts and
  stops at matching loop depth. Automated parent-region consistency now guards
  against recurrence.
- Failed jobs `118782904` and `118783012` were compile diagnostics, not model
  results. Redundant jobs `118783690` and `118783818` were cancelled after
  launcher-output ambiguity; neither is accepted evidence.

## Proposed AGENTS.md integration (not yet applied)

1. Preserve no-profile as the only final-score timing path.
2. Preserve the existing score profiler as the daily 4n64 DEMO gate and A/B
   reference chain.
3. Use diagnostic `summary` only when a broad region cannot distinguish the
   next hypothesis; do not require it for every optimization commit.
4. Use `trace` only after summary identifies a concurrency or imbalance
   question. Select one rank per node first and set an explicit event cap.
5. Require bitwise comparison, real node/local-rank metadata, zero dropped
   events, and diagnostic/parent consistency for accepted diagnostic evidence.
6. Record diagnostic/no-profile paired wall time as observer effect, but do not
   impose a small-overhead rejection threshold on summary or trace.
7. Never compare diagnostic wall directly with a score-profiler reference to
   accept a model optimization. Re-run the candidate with the score or
   no-profile binary after forming the hypothesis.
8. Keep Perfetto artifacts out of Git when large; commit the bounded bundle and
   document the remote path, size, hash, selected ranks, and event count.
