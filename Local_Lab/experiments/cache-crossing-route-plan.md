# Cache crossing-cell route plans

- Accepted anchor: `ddf22ce050af977cc36fec008173a29befef251e`.
- Reference: `cache-fine2coarse-route-plan-4n64-16ppn_20260806T065835Z_35945`.
- Targets: Grid 2 region 55 (`5.856541 s`), region 39 (`9.903396 s`), and
  region 49 (`3.330505 s`).
- Evidence: the `CellOwner+Receiver` crossing-block route rescans every
  `(cell, contact)` pair and rebuilds counts, displacements, and offsets for
  every coupled variable, although cell owners, receivers, contact order, and
  array shape are static.
- Hypothesis: cache ordered `(i,m)` send, receive, and zero records plus their
  buffer offsets under a route key isolated from the existing contact and F2C
  sum namespaces. Keep the original element order and `MPI_Alltoallv`.
- Calls without a crossing plan key retain the accepted implementation. No
  physical arithmetic, floating-point order, input, or profiling code changes.
- Expected numerical behavior: bitwise-identical output and lower region
  49/55/39 and total wall.
- Falsifier: any MPI/correctness failure, plan collision, changed call count,
  or no useful target/total improvement.

## Result: accepted

- Build job `118667931`; candidate
  `candidate_20260806T072105Z_3365`; binary SHA-256
  `3f3c39c3dc12293088c241b9cf47a2269e4dd88464658daa2a4509085c275ae2`.
- DEMO job `118668744`, run
  `cache-crossing-route-plan-4n64-16ppn_20260806T072734Z_65169`:
  normal end, complete outputs, and all 26 variables had `RMSE=0,
  max_abs=0`.
- Grid 2 region 49: `3.330505 -> 3.311041 s` (`-0.58%`). Region 55 and
  region 39 changed from `5.856541/9.903396 s` to `5.901155/9.988192 s`
  (`+0.76%/+0.86%`). Total improved from `78.541761 s` to `78.148727 s`
  (`-0.50%`), with material run-to-run variation in region 44 and Grid 1
  region 49. The targeted scan removal is directionally effective and the
  total path has no visible regression, satisfying the relaxed acceptance
  rule, but this is not considered a large performance result.
- Triggered 1-rank validation job `118669202`, candidate
  `candidate_20260806T073132Z_15199`: `passed=true`; candidate wall was
  `160.847 s` versus sealed baseline `188.695 s`. This timing is compatibility
  evidence only because the 64-rank crossing cache is inactive at 1 rank.
