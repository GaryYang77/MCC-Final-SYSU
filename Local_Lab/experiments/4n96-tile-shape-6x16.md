# 4n96 6x16 tile-shape screening experiment

- Accepted repository anchor: `be64888`.
- Frozen model-source anchor: `e7e0ce1`.
- Preserved score binary SHA-256:
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- Reference: 4 nodes, 96 ranks, 24 ranks/node, `8x12`, 60/300 steps,
  `Local_Lab/runs/profile128/tile-shape-control-8x12-4n96_20260809T125724Z_35720`.
- Candidate: same binary/ranks/steps with `6x16` tiles.

## Evidence and falsifiable hypothesis

The full `12x8` experiment improved nesting geometry but regressed Grid-2 R35
by `4.1%`; its shorter I-direction loops are the likely compute trade-off.
`6x16` gives each tile a longer contiguous I span than current `8x12`, which
should improve R22/R35 vector-loop efficiency.  With I varying fastest, each
24-rank node owns six complete four-rank J rows, so only 12 nearest-neighbour
tile edges cross the three node cuts (24 for `8x12`).

The countervailing risk is greater total internal-boundary length: for the
outer grid `6x16` has 7055 edge cells versus 6267 for `8x12`; the inner grid
has 4790 versus 4336.  The experiment is falsified if R22/R35 do not improve
enough to offset R39/R40/R41/R42/R49/R54/R55 growth.

This is a single score screening run, not a new 4n64 daily reference and not a
final speedup claim.  Binary, source, physics, input, rank count, precision,
profiling definitions and output validation remain unchanged.  It must end
normally and pass all 26 comparisons.  Only a material stable-region and total
advantage sufficient to project below the current full 2499.74 s result
warrants a full no-profile candidate.

## Result

- Score job `118843245`, run
  `Local_Lab/runs/profile128/tile-shape-candidate-6x16-4n96_20260809T183013Z_39381`.
  It ended normally and all 26 comparisons were bitwise zero.
- Versus the preserved 8x12 reference, Grid-2 score total changed
  `69.397 -> 67.092 s` (`-3.32%`).  R22 changed `5.596 -> 5.274 s`
  (`-5.7%`), R35 `9.749 -> 9.732 s` (neutral), R39
  `12.865 -> 11.523 s` (`-10.4%`), R49 `6.238 -> 4.646 s` (`-25.5%`), and
  R55 `8.483 -> 7.093 s` (`-16.4%`).  R40/R41/R42 regressed by roughly
  `3-9%`, as predicted from the greater internal-boundary length.

Decision: promote to one guarded full no-profile run.  Scaling the stable
R39/R49/R55 savings by their existing full-run costs projects enough benefit
to challenge the 2350-second goal.  The full launcher runs a same-allocation
60/300 no-profile preflight and aborts allocations slower than 90 seconds
before the complete three-day simulation.

## Full no-profile result

- Job `118843514`, nodes `j05r2n[04-07]`, preserved no-profile binary SHA-256
  `fe0049c067b8a0efec3385c49dd9e606001d91444f7fcf176990a9f8f99f9c1e`.
- Same-allocation 60/300 preflight:
  `Local_Lab/runs/profile128/final-6x16-preflight-20260809T183547Z_20260809T183551Z_24429`,
  wall `70.60 s`; the guarded 90-second slow-node cutoff passed.
- Complete 2592/12960 run:
  `Local_Lab/runs/profile128/final-6x16-full-noprofile-20260809T183547Z_20260809T183552Z_25778`,
  model wall `2461.22 s`.  It ended normally; output and comparison reports
  passed, and all 26 variables had `RMSE == 0` and `max_abs == 0`.
- The copied official `vali.py` differed only in `dir_test` and ended with
  `最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常`.

Decision: accept `6x16` as the fastest validated full 4n96 configuration, but
do not claim the project target.  It improves the prior `8x12` no-profile
result `2499.74 -> 2461.22 s` (`38.52 s`, `1.54%`) while remaining `111.22 s`
(`4.73%`) above the `2350 s` success threshold.  The score projection
overstated the full-run benefit, so further work must target the remaining
full-run cost rather than extrapolate another short score total alone.
