# In-place 1D floating-point assembly

- Accepted commit: `534ed011c3349bad6424d9fbae48b2a66111ab4f`.
- Model-source anchor: `e7e0ce1`.
- Daily gate: 4 nodes, 64 ranks, 16 ranks/node, `8x8`, 60/300 score
  PROFILE.
- Reference:
  `Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482`.
- Target: Grid-1/2 R49 point assembly and its enclosing R39/R55 nesting path.

## Hypothesis

The accepted boundary-flux batching first packs all four boundary directions
into a saved 1D `Fpack`.  `mp_assemblef_1d` then copies the complete array into
an automatic `Asend` array before `MPI_Allreduce`.  Tracer boundary batches are
large and R49 has disproportionate weight in the full 4n96 run.

Use the MPI-standard in-place form of the same `MPI_Allreduce` to reduce
directly into `A`.  This removes only the redundant local copy and its
temporary array.  Communicator, datatype, element count, operation, collective
call order, and per-element reduction are unchanged, so outputs are expected
to remain bitwise identical.  No non-DISTRIBUTE path is changed.

The hypothesis is supported only if the clean score gate passes with all 26
variables bitwise identical, unchanged R49 calls, lower R49 on both grids, and
no offsetting R39/R55 or stable-compute regression.  Build/runtime failure,
any numerical difference, or no useful target-region improvement falsifies it.

## Result

Accepted.

- Clean PROFILE build: job `118852090`, candidate
  `Local_Lab/runs/validation/candidate_20260809T222420Z_9333`, binary SHA-256
  `ff763073d469f1e36a42cc7cd5b12c14ee28d9cd57e38e3a9fd35bd4fe223632`.
- 4n64 score DEMO: job `118852220`, run
  `Local_Lab/runs/profile128/assemblef1d-in-place-4n64-16ppn_20260809T223055Z_41712`.
- Correctness: `passed=true`, normal end, complete outputs/profile, and all 26
  comparison variables have `RMSE=0` and `max_abs=0`.
- Target R49 improved with unchanged calls on both grids: Grid 1
  `3.2411 -> 2.3166 s` (`-28.53%`, 126592 calls), and Grid 2
  `3.2860 -> 3.0635 s` (`-6.77%`, 173120 calls).
- Profile total was effectively neutral (`68.166/68.169 -> 68.294/68.296 s`,
  `+0.19%`).  The known noisy Grid-1 R03 and R44 increased by about
  `0.34/0.78 s`; Grid-2 R40 also varied upward.  These non-target movements
  more than explain the small total difference.  Stable compute calls were
  unchanged, and R35 happened to move downward on both grids.
- R39/R55 were `+0.77/+1.21%` on Grid 2, small relative to their allocation
  variation and not sufficient to offset the causal R49 reduction.

The change affects an MPI collective buffer, so the communication acceptance
checks were applied explicitly: all ranks ended normally, outputs were
complete, no NaN/Inf or comparison error occurred, all 26 variables passed,
and R49 call counts were identical.  No independent 1-rank validation trigger
applies because the change is confined to the `DISTRIBUTE` path and produced
bitwise-identical DEMO output.
