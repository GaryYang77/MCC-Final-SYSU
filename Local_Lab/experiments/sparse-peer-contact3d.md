# Sparse active-peer routing for contact3d assembly

- Accepted anchor: `dbe0535aab17060d5d5a025a6f4ed95f950a5aad`.
- Reference: `direct-pack-contact3d-4n64-16ppn_20260806T175502Z_40915`
  (total `77.734 s`).
- Targets: Grid 1 region 49 (`3.901 s`) and Grid 2 region 49 (`3.340 s`).
  The accepted `mp_assemble_contact3d` still calls `MPI_Alltoallv` over all
  64 ranks even though each rank exchanges contact blocks with only the few
  donor/receiver tiles that overlap its contact points.
- Evidence: the cached route plan already contains per-rank
  `counts/displs/rcounts/rdispls`.  The active send/receive peer sets are
  static and can be stored in the plan.
- Hypothesis: replace the dense `MPI_Alltoallv` with a cached
  `Irecv -> Isend -> Waitall` exchange over active peers only.  Keep the
  exact same buffers, offsets, message order, and payload, so the result is
  bitwise identical, while reducing collective and idle cost on ranks whose
  contact sets are sparse.
- Scope: only the specialized `mp_assemble_contact3d` path accepted in
  `dbe0535`.  All generic `mp_assemble*` keyed paths keep `MPI_Alltoallv`.
  No profiling source changes.
- Correctness safety: the call sequence is identical on every rank (uniform
  `cr`/`gtype` loops and `UseLocalList`), so a module-local per-call tag
  counter is identical across ranks for the same call and prevents a send
  from one variable call from matching a receive from a later call.
- Expected numerical behavior: bitwise-identical output and lower region
  49 and total wall.
- Falsifier: MPI hang/error, tag mismatch, changed call count, nonzero
  DEMO comparison error, or no useful target/total improvement.

## Result: accepted

- Build job `118691992`; candidate
  `candidate_20260806T181336Z_4057`; binary SHA-256
  `c02aaf55a89c088d56813f0aca07197978f5fde620e275860556522406149ae1`.
- DEMO job `118692267`, run
  `sparse-peer-contact3d-4n64-16ppn_20260806T181956Z_31080`: normal end,
  complete outputs, and all 26 variables had `RMSE=0, max_abs=0`.
- Grid 1 region 49: `3.901 -> 3.367 s` (`-13.7%`); Grid 2 region 49
  `3.340 -> 3.346 s` (unchanged path, run noise). Total changed from
  `77.734 s` to `76.450 s` (`-1.65%`). Region 49 call counts are unchanged;
  Grid 1 region 44 broadcast varied `4.863 -> 3.352 s` and Grid 2 region 44
  `1.532 -> 1.898 s`, consistent with the known run-to-run broadcast noise
  and not attributable to this change.
- The active-peer exchange posts `Irecv` for every receive peer before
  `Isend`, uses a module-local per-call tag so a message from one variable
  call can never match a receive from a later call, and keeps the exact
  buffers, offsets, and unpack order of the accepted `MPI_Alltoallv`
  implementation.
- Triggered 1-rank validation job `118692336`, candidate
  `candidate_20260806T182259Z_11427`: `passed=true`; candidate wall was
  `156.405 s` versus sealed baseline `188.695 s`. The 1-rank path exercises
  the self-peer sparse exchange and is supporting compatibility evidence;
  the DEMO comparison is the distributed correctness gate.
