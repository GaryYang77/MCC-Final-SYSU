# Gather only owner-computed fine-to-coarse block sums

- Accepted anchor: `87cf5938c2a17f58d853787157a4007e984f6a8f`
- Reference run: `Local_Lab/runs/profile128/scatterv-input-fields-2n64_20260804T142758Z_12148`
- Reference binary SHA-256: `4aeccdcce76f414e19e3dfa05fc3a8ed6529278bde93498bd6547b4ba2d8c8dc`
- Reference wall: `162.99 s`
- Target: Grid 2 region 49 (`mpi_point_gathering`), `28.9961 s`, inside
  region 55 (`fine_to_coarse`), `30.5510 s`.

## Falsifiable hypothesis

The equal-vertical-level, non-area-averaged fine-to-coarse path already
classifies every donor block as either wholly owned by one MPI rank or crossing
a tile boundary.  For wholly owned blocks, only `BlockOwner(m)` computes the
ordered vertical record `Fsum(:,m)`; all other ranks contribute zeros.  Passing
this existing ownership map to the owner-aware `mp_assemble` implementation
will gather only the unique records instead of applying an all-reduce to the
entire zero-filled `Klen*Npoints` array.

Expected DEMO evidence:

- Grid 2 region 49 and region 55 wall decrease, with their call counts
  unchanged;
- total wall does not show a clear regression;
- the complete-block results remain bitwise identical because the same owner
  computes every sum in the same loop order;
- blocks crossing tile boundaries remain on the existing `Fcross` reduction
  and reconstruction path;
- configurations without one rank per tile retain the existing all-reduce
  fallback inside `mp_assemble`.

This changes only transport of already-computed block sums.  Input data,
physical equations, masks, averaging, time steps, and profiling
instrumentation are unchanged.

## Accepted result

- Validation: job `118560924`, candidate
  `candidate_20260804T143831Z_9553`, binary SHA-256
  `bdcdfeafbd1f48c6c0725c3f336470a451d12a237ebab01ae2768c4c668da08d`;
  exit 0, `[validate] PASS`, report `passed=true`.
- DEMO: job `118561202`, run
  `owner-aware-fsum-2n64_20260804T144713Z_56459`; `passed=true`,
  `normal_end=true`, `comparison.passed=true`, with all 26 entries at zero
  RMSE and zero max-absolute error.
- Grid 2 region 49 decreased from `28.996115 s` to `27.821706 s`
  (`4.05%`), with unchanged aggregate calls (`9272064`).  Region 55
  decreased from `30.551010 s` to `28.999527 s` (`5.08%`).
- Resource wall changed from `162.99 s` to `163.39 s` (`+0.25%`), which is
  neutral at the resolution of a single DEMO run.  Grid 1 region 49 varied
  from `39.3422 s` to `42.3883 s` even though this change is confined to the
  fine-to-coarse path; no repeat was requested at this stage.
- The cumulative demonstrated result therefore remains the previous
  `162.99 s`, or `42.42%` below the original `283.07 s` daily baseline.

Tentatively accepted under the team's relaxed rule: the intended path improves
without a clear total-wall regression, and numerical output is bitwise
identical.  This result is not claimed as an additional cumulative speedup.
