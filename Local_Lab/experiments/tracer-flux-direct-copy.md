# Tracer flux direct-copy experiment

## Contract

- Branch: `perf/tracer-flux-direct-copy`.
- Accepted commit: `0f7e5c4`.
- Comparison channel: `exact`.
- Target: `assemble_tracer_fluxes` pack/unpack memory work only. MPI collective,
  payload, element order, call count, nesting behavior, inputs, and outputs stay
  unchanged.

## Evidence and hypothesis

Diagnostic job `118955359` measured Grid-2 assembly at `3.2544 s`: pack
`0.4991 s`, MPI `1.9691 s`, and unpack `0.7839 s`. The two copy phases consume
`1.2830 s` and use `RESHAPE` expressions that may materialize temporaries.

The candidate replaces each `RESHAPE` assignment with an explicit
`itrc/k/i` loop whose innermost index is the contiguous first Fortran
dimension. West/east and south/north copies share their loop traversal, while
their offsets preserve the original packed array order exactly. The expected
effect is lower temporary-memory traffic in sites 189 and 191; site 190 MPI
time, payload, peers, and all numerical values should remain unchanged.

The entire assembly is below 5% of the accepted DEMO total, so this experiment
cannot authorize a full three-day run by itself. If its exact score DEMO is
effective, it is an accumulated compute optimization only.

## Results

- Clean score build: Slurm job `118955508`, candidate
  `Local_Lab/runs/validation/candidate_20260811T150645Z_30239`, binary SHA-256
  `98be8b4a3c11e548596ac00ab9a6b9b1e2d3ed0270c867919490e8febd67f485`.
- Score DEMO: Slurm job `118955758`, run
  `Local_Lab/runs/profile128/tracer-flux-direct-copy-4n64-16ppn_20260811T151359Z_47837`.
  It ended normally and all 26 variables were bitwise identical to the
  accepted reference.
- Score total moved from `68.2957 s` to `67.7689 s` (`-0.77%`). Grid-2 R35
  moved from `7.3638 s` to `7.0812 s` (`-3.84%`); Grid-1 R35 moved from
  `2.8766 s` to `2.8474 s` (`-1.02%`).
- Diagnostic build: Slurm job `118955514`, binary
  `Local_Lab/builds/profiling/diagnostic_20260811T150710Z_3552/bin/oceanM`,
  SHA-256
  `afa5e9d7e05a55e09886c1ce7d75d90915ebacb22f50892720556141514a704f`.
- Diagnostic summary: Slurm job `118955757`, run
  `Local_Lab/runs/profile128/tracer-flux-direct-copy-diagnostic-summary_20260811T151350Z_37526`.
  Grid-2 pack fell from `0.4991 s` to `0.3584 s` (`-28.2%`) and unpack from
  `0.7839 s` to `0.5833 s` (`-25.6%`); parent assembly fell from `3.2544 s`
  to `2.8867 s` (`-11.3%`). Grid-1 pack/unpack fell by about 34.6%/32.2%,
  and its parent assembly fell from `1.3238 s` to `1.1802 s` (`-10.9%`).
  MPI payload, peers, and calls were unchanged; Grid-2 MPI moved only from
  `1.9691 s` to `1.9427 s`, confirming that the measured gain is in the two
  targeted memory-copy phases.

**Decision: accept as an exact accumulated compute optimization.** The target
phases and enclosing R35 improve in the predicted direction with no numerical
change. The credible DEMO total reduction is only 0.77%, below the required 5%
full-run trigger, so no no-profile full three-day task or official validation
is launched for this individual candidate.
