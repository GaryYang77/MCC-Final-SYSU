# Disable inactive mass-flux diagnostics

- Accepted anchor: `58a4e25`
- Reference run:
  `Local_Lab/runs/profile128/batch-tracer-boundary-flux-4n64-16ppn_20260805T123120Z_12354`
- Reference binary SHA-256:
  `a0507ac874de64221fcfeea7aeaaa565f8b496be5d24f858c7a741b8a425b323`
- Reference PROFILE total mean: `108.080020 s`.
- Reference region 49: Grid 1 `21.087661 s`, `28078` calls per rank;
  Grid 2 `13.260396 s`, `3005` calls per rank.

## Falsifiable hypothesis

The refinement driver invokes `check_massflux` after each initial,
predictor, and corrector 2D nesting phase. The routine documentation and both
`main2d.F`/`main3d.F` call-site comments explicitly classify it as diagnostic.
Its computed conjugate `BRY_CONTACT%Mflux` values are only read by this same
diagnostic path; numerical output and subsequent state updates do not consume
them. Detailed reporting is compiled only with `NESTING_DEBUG`, which is not
defined by the competition application.

When `NESTING_DEBUG` is absent, skip `check_massflux` and the preceding global
assembly whose sole consumer is that check. Keep all boundary-condition state
updates and MPI halo exchanges unchanged, and retain the complete original
behavior in a `NESTING_DEBUG` build.

Expected 4n64-16ppn DEMO evidence:

- region 49 calls and wall decrease substantially on the fast 2D path;
- total PROFILE wall decreases without moving time to another MPI region;
- all 26 comparisons remain bitwise identical and the model ends normally;
- enabling `NESTING_DEBUG` at preprocessing time still compiles the original
  diagnostic calls and mass-flux assembly.

No physical equation, state update, input, timestep, precision, compiler flag,
or profiling source is changed.

## Result

- Clean build: job `118629960`, PASS; candidate
  `Local_Lab/runs/validation/candidate_20260805T124432Z_13790`; binary SHA-256
  `f6f5ccefd519fa98fb58dad0b2fdde987c10fafcc2c558a7c1e4fa03ff1a1908`.
- 4n64-16ppn DEMO: job `118630864`, PASS; run
  `Local_Lab/runs/profile128/no-inactive-massflux-diagnostic-4n64-16ppn_20260805T125043Z_40398`.
- Correctness: normal end; all 26 comparisons have `RMSE=0` and
  `max_abs=0`.
- PROFILE total mean: `108.080020 s` to `104.429175 s` (`-3.38%`).
  Slurm elapsed wall: `110.76 s` to `106.36 s` (`-3.97%`).
- Grid 1 region 49 calls per rank: `28078` to `1978` (`-92.96%`);
  wall mean: `21.087661 s` to `16.813368 s` (`-20.27%`).
- Grid 2 region 49 calls per rank: `3005` to `2705` (`-9.98%`);
  wall mean remained effectively flat (`13.260396 s` to `13.314451 s`).
- Peak RSS decreased from `819148 KiB` to `813012 KiB`.

Accepted: the unused diagnostic path accounted for the predicted high-frequency
collectives, total wall improved materially, and all numerical output remained
bitwise identical. `NESTING_DEBUG` builds retain the original check and its
required mass-flux assembly.
