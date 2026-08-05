# Route runtime contact records only to receiver ranks

- Accepted anchor: `f273945bc763d6fb484400472f84d781e20b8eed`
- Reference: `cache-local-contact-index-4n64-16ppn_20260805T135252Z_12578`
- Target: Grid 1/2 region 49, `16.326885 s` and `13.319466 s` mean wall.
- Hypothesis: runtime `get_refine` records have one donor owner and one
  receiver tile, but owner-aware `MPI_Allgatherv` replicates every record to
  all 64 ranks. `put_contact2d/3d` subsequently reads only records inside the
  current receiver tile. Cache that receiver owner and use `MPI_Alltoallv` to
  copy each record directly from its donor owner to its sole consumer.
- Scope: only runtime `get_refine` enables targeted routing. Initialization,
  composite-grid, generic owner-aware assembly, and fine-to-coarse paths keep
  their accepted collectives.
- No floating-point reduction or interpolation order changes. All ranks still
  participate, including ranks with zero send or receive records.
- Expected numerical behavior: bitwise-identical output, unchanged R49 calls,
  substantially lower R49 and R53 wall.
- Falsifier: missing receiver ownership, abnormal MPI termination, comparison
  failure, or clear total-wall regression.

## Result

- Clean build job `118633393`, candidate
  `candidate_20260805T140530Z_8486`, binary SHA-256
  `ec4e187699139ac88d923ad651e88c50656504faeff69514e5ad3509b72d67e8`.
- DEMO job `118633585`, run
  `route-contact-to-receivers-4n64-16ppn_20260805T141157Z_33790`, completed
  normally with `passed=true`, `comparison.passed=true`, and all 26 variables
  at `RMSE=0`, `max_abs=0`.
- Profile total mean fell from `101.74494 s` to `90.332585 s` (`-11.22%`),
  and Slurm wall fell from `103.57 s` to `92.21 s`.
- Grid 1 region 49 fell from `16.326885 s` to `4.808523 s` (`-70.55%`),
  and region 53 fell from `13.495853 s` to `1.829743 s` (`-86.44%`).
  Their call counts were unchanged.
- Grid 2 region 49 rose from `13.319466 s` to `13.866949 s` in this single
  run, but the intended path saved `11.66 s` inside Grid 1 nesting and total
  wall improved by `11.41 s`. Peak RSS changed from `815364` to `816268 KiB`
  (`+0.11%`).

Decision: accept. Direct donor-to-receiver routing removes unnecessary global
replication, produces a large total improvement, and remains bitwise exact.
