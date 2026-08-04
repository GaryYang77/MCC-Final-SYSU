# Sparse contact ownership assembly

- Accepted anchor: `0cc192066a41f715947eb586c0ab2444fc6a1a20`
- Reference run: `Local_Lab/runs/profile128/recovery-hybrid-after-batch-2n64_20260804T131350Z_11076`
- Reference binary SHA-256: `38453300bed97412c70bb6fc2c67f3340018865a248c647ae6fd778055b7e8fb`
- Reference wall: `211.72 s` (fresh recovery run; the original accepted hybrid
  measurement was `220.61 s`).
- Target: Grid 1 region 49/53 contact assembly; Grid 2 region 49 is a
  secondary target.

## Falsifiable hypothesis

Each contact datum is owned by one donor tile, while the current
`mp_assemble` sends a full zero-filled contact array from every rank through
`MPI_Allreduce`.  Cache the owner rank and rank-ordered packing map for every
R/U/V contact region, pack only locally owned values, and use one
`MPI_Allgatherv` to reconstruct the complete contact array on all ranks.

Expected DEMO evidence:

- collective call count is unchanged, avoiding the failed tracer-batching
  protocol change;
- bytes contributed by a rank scale with its owned contact points rather than
  total contact points;
- Grid 1 region 49 and 53 wall decrease without increasing peak RSS
  materially;
- the packed result is bitwise identical because ownership is unique and no
  floating-point reduction is needed;
- all ranks, including ranks owning zero contact points, still participate in
  the collective and receive the complete buffer.

The cached maps must be constructed outside the time-stepping hot path.  No
profiling instrumentation, interpolation, physical equations, input data, or
time-step counts may change.

## Intermediate gate result

- Job `118557981`, candidate `candidate_20260804T133105Z_16675`: clean Intel
  build succeeded, but the model stopped in `set_contact` with exit flag 5.
- Cause: the first owner-map version incorrectly required every contact entry
  to have an owner.  Existing U/V staggered boundary arrays contain legitimate
  unowned placeholders which the old zero-filled Allreduce leaves at zero.
- Correction: retain `Downer=-1`, omit those records from Allgatherv, and
  explicitly restore their output records to zero.  This is a correctness fix
  within the same sparse-contact hypothesis; no profiling run was submitted.
- Job `118558278`, candidate `candidate_20260804T134023Z_26519`: model ended
  normally but all 26 variable comparisons failed (largest errors in refined
  grid TIC/oxygen).  The candidate wall was `188.413 s`, but failed numerical
  results make that timing inadmissible.
- Cause: `set_contact` runs before final parallel `BOUNDS` are available, so
  eager owner construction classified real donor points as unowned.  Owner
  maps are now initialized with sentinel `-2` and constructed once, lazily, at
  the first `get_contact2d/3d` call after tile bounds are established.

## Accepted result

- Validation: job `118558690`, candidate
  `candidate_20260804T135335Z_6591`, binary SHA-256
  `cca7aad0237cc6c8e7c841e5c55d46444c9b8c7e526564c6136066389a933753`;
  exit 0, `[validate] PASS`, report `passed=true`.
- DEMO: job `118559018`, run
  `sparse-contact-allgatherv-2n64_20260804T140306Z_26445`; `passed=true`,
  `normal_end=true`, `comparison.passed=true`, with all 26 entries at zero
  RMSE and zero max-absolute error.
- Resource wall changed from `211.72 s` to `211.57 s` (`-0.07%`, neutral).
- Grid 1 region 53 decreased from `24.211704 s` to `18.125096 s`
  (`-25.1%`), and region 49 from `44.216880 s` to `41.834600 s`
  (`-5.4%`).
- System CPU time decreased from `374.33 s` to `259.78 s` (`-30.6%`), while
  maximum RSS increased slightly from `819500 KiB` to `825492 KiB` (`+0.7%`).
- Grid 2 region 49 increased from `28.326211 s` to `30.018814 s` and region
  55 from `29.921083 s` to `30.705697 s`; retain this as a cumulative A/B
  watch item.

Accepted under the team's revised rule: the communication logic is valid,
the intended donor path improves substantially, and total wall has no clear
regression.  A later cumulative no-profile comparison may still revert it if
the Grid 2 cost dominates outside the DEMO.
