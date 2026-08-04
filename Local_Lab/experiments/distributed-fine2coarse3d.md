# Distributed 3D fine-to-coarse averaging experiment

- Accepted commit / rollback anchor: `b6c435b6bd7cc4bf398e916dda6d7e630fb283cd`
- Branch: `perf/distributed-fine2coarse`
- Accepted reference: `Local_Lab/runs/profile128/recovery-mask-reuse-2n64_20260804T110048Z_49545`
- Reference binary SHA-256: `c1dedc4fdafc71fab250e30d4fd4d768c4ba304f0884633e6a85189888aaa116`

## Falsifiable hypothesis

Grid 2 region 46 spends about 56 seconds aggregating complete fine-grid fields
onto every rank before 3D fine-to-coarse averaging. For refinement ratio three,
the output contact buffer is roughly one ninth of the horizontal fine-grid
field, and each output is only a masked sum and count over its 3x3 donor block.

For simple averaging with matching vertical levels, let each rank compute the
partial sums and wet-point counts contributed by the fine cells it owns, then
sum only the coarse contact buffers with the existing `mp_assemble` reduction.
Cache counts across consecutive tracers within the same coupling section, as
the accepted mask-reuse optimization already establishes is valid. Preserve
the original full-field path for area averaging or mismatched vertical bounds.

The optimization should eliminate 3D full-field region-46 aggregations and
reduce communication volume by approximately the refinement-area ratio. It
may move communication time into region 49 because it reuses the existing
instrumented sum reduction. Total wall and combined regions 46/49 must improve;
all validation and DEMO comparisons must pass. A different MPI reduction order
may produce nonzero but tolerance-compliant numerical differences.

## Build attempt 1

- Validation job `118552354`, candidate
  `candidate_20260804T111919Z_6366`, stopped during compilation before any
  model run or comparison.
- Cause: while importing `mod_parallel` into `fine2coarse3d`, the original
  top-level `nesting` import was accidentally removed, leaving
  `first_tile/last_tile` without explicit types.
- Corrective action: restore the original top-level import, retain the new
  local import, rerun preprocessing and local tests, then rebuild from clean
  source. No performance or numerical result exists for this attempt.

## Partial-sum attempt

- Validation: job `118552717`, candidate
  `candidate_20260804T112510Z_12527`, binary SHA-256
  `9d8ed2d478dc5b71acb4ad96a64e5294111f15ebce74e53556747da31b371561`;
  wrapper exit zero, `[validate] PASS`, and `passed=true`.
- 64-rank profiling: job `118553370`, run
  `distributed-fine2coarse3d-2n64_20260804T113530Z_1544`; model ended
  normally and outputs were complete, but `comparison.passed=false`.
- Wall fell from 245.32 to 190.28 seconds (-22.44 percent). Grid 2 region 55
  fell from 58.20 to 7.86 seconds and region 46 disappeared; Grid 2 region 49
  rose from 4.37 to 8.26 seconds.
- The changed cross-rank addition order exceeded tolerance after 300 steps:
  maximum absolute errors included `oxygen=7.72e-3`, `TIC=5.62e-3`, and
  `detritus=3.68e-3`.

The partial-sum representation is rejected despite its performance. Refine the
same contact-only hypothesis by assembling raw 3x3 donor blocks: each element
has one nonzero owner, then every rank applies the original J/I summation order.
This should retain most of the communication/unpack benefit while restoring
the original floating-point arithmetic sequence.

## Raw-block attempt

- Validation: job `118553820`, candidate
  `candidate_20260804T114723Z_25485`, binary SHA-256
  `6137287becea2b5c67c20d755f3696da359640f5cfa61a419d2d739448ecc916`;
  wrapper exit zero, `[validate] PASS`, and `passed=true`.
- Profiling: job `118554437`, run
  `contact-block-fine2coarse3d-2n64_20260804T120129Z_1014`;
  `passed=true`, `normal_end=true`, `comparison.passed=true`, and all 26
  comparisons returned to `RMSE=0`, `max_abs=0`.
- Exact arithmetic came at excessive communication cost: wall regressed from
  245.32 to 469.53 seconds. Grid 2 region 49 rose from 4.37 to 200.00 seconds,
  and region 55 rose from 58.20 to 216.96 seconds.

Reject the all-raw representation. Refine the same hypothesis with a hybrid:
blocks contained within one tile transmit one ordered block sum, while only
blocks crossing tile boundaries transmit nine raw values. This preserves the
original order for both classes and compresses the majority of contact data.

## Hybrid result and decision

- Local checks: MPI preprocessing, `git diff --check`, and 42 tests passed.
- Validation: job `118555260`, candidate
  `candidate_20260804T121749Z_26310`, binary SHA-256
  `38453300bed97412c70bb6fc2c67f3340018865a248c647ae6fd778055b7e8fb`;
  wrapper exit zero, `[validate] PASS`, and `passed=true`.
- Profiling: job `118555580`, run
  `hybrid-contact-fine2coarse3d-2n64_20260804T122638Z_2779`;
  `passed=true`, `normal_end=true`, `comparison.passed=true`, outputs complete,
  and all 26 comparisons have `RMSE=0`, `max_abs=0`.
- Slurm wall fell from 245.32 to 220.61 seconds (-10.07 percent). Relative to
  the initial 283.07-second 2-node accepted baseline, cumulative wall is down
  22.06 percent.
- Grid 2 region 55 fell from 58.20 to 31.26 seconds and full-field region 46
  disappeared. Grid 2 region 49 rose from 4.37 to 30.33 seconds, so the data
  flow still saves about 27 seconds net in the target section.
- Peak RSS fell slightly from 815552 to 812876 KiB. Total rank imbalance stayed
  near one (`1.000044`).

Decision: accept. The hybrid representation removes complete-field replication,
preserves the original per-block floating-point order exactly, produces a clear
total-wall improvement, and has no memory or correctness regression. This run
becomes the next accepted 2-node reference.
