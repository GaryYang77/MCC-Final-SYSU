# MCC profiler v2 design and acceptance contract

## Scope and frozen baseline

- Source anchor: `2195306c` (`perf(biology): skip tile-local dry rows`).
- The existing `PROFILE_RANK` lines, region IDs 0--56, JSON/CSV fields, and
  `profile_bundle.json` remain the score-profiler compatibility contract.
- The accepted 4n64 score reference is
  `tracer-vdiff-direct-rhs-4n64-16ppn_20260807T151528Z_54133`; the subsequent
  biology candidate preserved all 26 comparison metrics bitwise and measured
  Grid-1 R15 at 1.063--1.070 s in three allocations.
- Historical alternating-order measurement puts score-profiler overhead near
  +0.89%. Phase D will remeasure the final source; the historical value is not
  accepted as proof for profiler v2.

Profiler v2 changes instrumentation only. It must not alter model equations,
input, output cadence, precision, tile decomposition, MPI payloads, or the
existing score timing definitions.

## Diagnostic questions

The v1 region totals cannot answer the questions now blocking optimization:

1. R49: which assembly path is expensive, and how much is local preparation,
   packing/direct accumulation, MPI wait, or unpacking?
2. R35: after vertical-factorization and RHS-load reuse, which tracer phase is
   the remaining compute bottleneck?
3. R44: which broadcast type and payload class causes the variable wall time?
4. R40--R42: is halo imbalance caused by packing, late arrival/MPI wait, or
   unpacking, and which ranks/nodes are consistently slow?
5. R54/R55: how much nesting time is interpolation/local work versus routed
   communication?

## Modes

The compile-time `PROFILE_DIAGNOSTIC` switch keeps all diagnostic calls out of
the score binary. A diagnostic binary selects one runtime mode:

- `summary` (default): streaming per-site aggregates and per-rank records;
- `trace`: the same summary plus bounded per-call events in selected ranks;
- `score`: accepted for launcher compatibility but emits no diagnostic data.

The score build remains the ordinary `PROFILE` build without
`PROFILE_DIAGNOSTIC`.

## Summary schema

Each stable integer site has a mapping containing `site_id`, parent region,
category, operation, phase, and name. At model finalization each rank emits one
record per active site:

```text
PROFILE_SITE rank node local_rank grid model site parent category phase
             calls wall bytes_sent bytes_recv peers_max events_dropped
```

The parser computes rank distributions (min/mean/median/p95/max, standard
deviation, slow ranks), totals, bytes/call, and time/call. Existing v1 records
are parsed unchanged. Diagnostic records are optional and absence is valid for
score/no-profile runs.

Sites are mutually exclusive only when explicitly documented as phases of the
same operation. The report must not add unrelated inclusive timers.

## Trace schema

Trace mode stores events in a fixed-size in-memory buffer and writes only at
model finalization. Each event contains rank, grid/model, site, start/end time,
bytes, peer count, and sequence. No event performs file or stdout I/O in a hot
path.

Environment controls:

```text
MCC_PROFILE_MODE=score|summary|trace
MCC_TRACE_RANKS=all|comma-separated ranks
MCC_TRACE_MAX_EVENTS=<positive integer, capped by the build>
MCC_PROFILE_DIAG_DIR=<run directory>
```

The launcher chooses conservative defaults. Overflow increments
`events_dropped`; it never wraps and silently overwrites evidence.

Each rank writes one line-oriented diagnostic log at finalization. A Python converter
validates metadata and emits an offline Perfetto-compatible JSON trace. MPI
rank is represented as a process, site slices as tracks, and bytes/peers as
event arguments. Cross-rank timestamps use explicit start/end clock-calibration
metadata; the report records calibration RTT and does not claim alignment when
metadata is missing.

## Phase-D acceptance gates

All measurements use 4 nodes, 64 ranks, 16 ppn, 8x8 tiles, and 60/300 steps.

1. Local tests: all `Local_Lab/tests` pass, including backward compatibility,
   malformed diagnostics, rank statistics, overflow reporting, and Perfetto
   conversion.
2. Build: clean score, diagnostic, and no-profile binaries build with the
   official Intel/HPC-X/NetCDF stack; hashes are recorded.
3. Correctness: score, summary, trace, and no-profile runs end normally and all
   26 comparison metrics have `RMSE=0` and `max_abs=0`.
4. Score overhead: at least three alternating-order score/no-profile pairs;
   median overhead <=1.0% and no unexplained systematic regression.
5. Summary observer effect is measured in a same-allocation pair and recorded
   beside every report. It is not a score gate: summary is accepted when the
   score/no-profile path remains unchanged, numerical results are exact, and
   phase/site evidence is internally consistent. Large overhead is a warning
   that timings may be perturbed, not a reason to weaken diagnostic fidelity.
6. Trace is diagnostic only: bounded run artifacts, no dropped events under the
   prescribed DEMO configuration, and total trace data <=256 MiB.
7. Evidence: site counts, bytes, phase coverage, rank/node metadata, clock
   calibration, and Perfetto export are present and internally consistent.
   Diagnostic operation totals must not exceed their unchanged parent region
   by more than 10%; contact/f2c child phases must cover 90--110% of their
   operation total. This catches misplaced timer boundaries before hotspot
   evidence is accepted.

Failure of any gate prevents freezing profiler v2 or changing `AGENTS.md`.
