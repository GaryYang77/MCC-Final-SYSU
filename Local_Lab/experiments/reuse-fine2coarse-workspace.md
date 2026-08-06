# Reuse fine2coarse3d work arrays

- Accepted anchor: `76f549f7d31367aa73da5f4d20d383850ece4999`.
- Reference: `cache-get-contact3d-route-plan-4n64-16ppn_20260806T060558Z_28995`.
- Target: Grid 2 region 55 (`5.985186 s`) and its enclosing region 39
  (`10.029551 s`).
- Evidence: the distributed `fine2coarse3d` path allocates, clears, and
  deallocates `Fsum` and (when needed) `Fcross` on every variable call. The
  active dimensions repeat across the tracer sequence.
- Hypothesis: retain thread-private module workspaces, grow each dimension on
  demand, and clear only the active slice. This removes repeated allocation
  and deallocation while keeping the active array shape, initialization,
  accumulation loops, and MPI payload unchanged.
- No physical arithmetic, floating-point order, MPI operation, input, or
  profiling code changes.
- Expected numerical behavior: bitwise-identical output and lower region
  55/39 and total wall.
- Falsifier: any build/MPI/correctness failure, changed call count, or no
  useful target/total improvement.

## Result: accepted

- Build job `118664409`; candidate
  `candidate_20260806T062642Z_5499`; binary SHA-256
  `1a29bc9aee6de0c45f1641a0a7af10d3e25e53088f6f0fc197b7cf014de67662`.
- DEMO job `118664929`, run
  `reuse-fine2coarse-workspace-4n64-16ppn_20260806T063348Z_17558`:
  normal end, complete outputs, and all 26 variables had `RMSE=0,
  max_abs=0`.
- Grid 2 region 55: `5.985186 -> 5.837665 s` (`-2.46%`); enclosing
  region 39: `10.029551 -> 9.914756 s` (`-1.14%`). Total improved from
  `79.501144 s` to `78.041478 s` (`-1.84%`). Grid 1 region 39 also improved
  from `1.933177 s` to `1.892105 s` (`-2.12%`).
- No triggered 1-rank validation: the distributed DEMO was bitwise identical,
  and the change did not alter numerical order, MPI behavior, precision,
  boundaries, masks, CPP selection, or a fallback path.
