# Cache locally owned donor contact indices

- Accepted anchor: `5774092b1ceaf3e0e67a45cd1a1b3cde2f06df6b`
- Reference: `cache-fine2coarse-block-map-4n64-16ppn_20260805T133300Z_62076`
- Target: Grid 1 region 53 (`ngetD`), `13.822807 s` mean wall.
- Hypothesis: `get_contact2d/3d` already caches the unique owner of every
  contact point, but every MPI rank still scans every point on every call and
  rejects non-local points with a bounds test. Cache the ascending indices
  owned by `MyRank` together with the owner map and iterate only those indices
  in the one-rank-per-tile path.
- Communication calls, packed records, contact ordering, and floating-point
  assignments are unchanged. Configurations without one rank per tile retain
  the full scan.
- Expected numerical behavior: bitwise-identical output.
- Falsifier: DEMO comparison failure or a clear total-wall regression.

## Result

- The first clean build, job `118632910`, stopped at compile time because
  local loop variable `n` conflicted case-insensitively with the `N` array
  imported from `mod_param`. No model run was attempted; renaming it to `idx`
  fixed the declaration without changing the experiment.
- Corrected clean build: job `118632980`, candidate
  `candidate_20260805T134639Z_2023`, binary SHA-256
  `8be1dcb5bb0ecf22882766112b911b7d7857aa893c4cdcf4dc2f8b3e6c93a53c`.
- DEMO job `118633093`, run
  `cache-local-contact-index-4n64-16ppn_20260805T135252Z_12578`, completed
  normally with `passed=true`, `comparison.passed=true`, and all 26 variable
  comparisons at `RMSE=0`, `max_abs=0`.
- Profile total mean fell from `102.69084 s` to `101.74494 s` (`-0.92%`),
  and Slurm wall fell from `104.70 s` to `103.57 s`.
- Grid 1 region 53 fell from `13.822807 s` to `13.495853 s` (`-2.37%`).
  All target and MPI call counts were unchanged. Peak RSS fell slightly from
  `816044` to `815364 KiB`.

Decision: accept. The intended extraction path and total wall both improve,
with unchanged communication protocol and bitwise-identical results.
