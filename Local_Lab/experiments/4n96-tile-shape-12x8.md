# 4n96 12x8 tile-shape experiment

- Accepted repository anchor: `731bb6a5fa1eaccbca2ab9b28109ed8860e7791f`.
- Frozen model-source anchor: `e7e0ce1` (`perf(biology): hoist shallow-water light factor`).
- Preserved score binary SHA-256:
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- Control configuration: 4 nodes, 96 ranks, 24 ranks/node, `8x12` tiles,
  60/300 steps.
- Candidate configuration: the same allocation, binary, ranks, input, and
  step counts, with `12x8` tiles as the only changed variable.

## Falsifiable hypothesis

ROMS maps rank/tile IDs with I varying fastest (`Itile=tile-Jtile*NtileI`).
Both `8x12` and `12x8` put an integral number of complete J rows on each
24-rank node, so neither shape introduces a partial row at a node boundary.
For the 361x328 outer grid, `12x8` also reduces the geometric internal-boundary
length from 6267 to 6135 cells and makes the compute tiles less elongated.
The 237x247 inner grid changes from 4336 to 4378 cells, a small increase.

If the current `8x12` shape is paying excess Grid-1 halo/compute imbalance,
`12x8` should reduce same-allocation total wall without materially increasing
Grid-2 R39/R40/R41/R42/R49. Calls may redistribute by direction, but the
top-level time-step call counts and numerical outputs must remain valid.

This is a run-configuration experiment. It changes no source, physics,
profiling definitions, inputs, output cadence, MPI rank count, or numerical
tolerance.

## Gate and decision

Run the control and candidate sequentially in one exclusive allocation. Both
runs must end normally, produce all outputs, and pass the 26-variable comparison
including shape, mask, NaN/Inf, RMSE, and max-absolute-error checks. Compare
total wall plus R35/R39/R40/R41/R42/R49/R54/R55 on both grids. R03/R44 are
reported separately as volatile regions.

Reject `12x8` if it fails correctness, hangs, or does not show a useful total
or communication-path improvement after accounting for R03/R44. A promising
result must be confirmed in the same 4n96 configuration before any full run.

## Result

Job `118832255` ran the control first and candidate second on the same
`j05r2n[00-03]` allocation. Exact run directories:

- control:
  `Local_Lab/runs/profile128/tile-shape-control-8x12-4n96_20260809T125724Z_35720`;
- candidate:
  `Local_Lab/runs/profile128/tile-shape-candidate-12x8-4n96_20260809T125724Z_35720`.

Both runs ended normally and produced complete outputs. The candidate's
26-variable comparison against the control was bitwise identical
(`max RMSE=0`, `max_abs=0`). The staged binary hash in both reports is the
preserved `d29d1f...8220` score binary.

The control/candidate Slurm walls were `71.78/69.04 s` (`-3.82%`) and Grid-2
R0 means were `69.397/67.106 s` (`-3.30%`). The selected Grid-2 regions moved
as follows:

| Region | 8x12 (s) | 12x8 (s) | Change |
| --- | ---: | ---: | ---: |
| R35 tracer corrector | 9.749 | 10.144 | +4.1% |
| R39 nesting | 12.865 | 10.942 | -14.9% |
| R42 4-D halo | 5.467 | 6.271 | +14.7% |
| R49 point gathering | 6.238 | 3.877 | -37.9% |
| R54 put receiver data | 4.375 | 4.872 | +11.4% |
| R55 two-way coupling | 8.483 | 6.064 | -28.5% |

Call counts were unchanged. Grid-1 R40/R41/R49 also improved, while Grid-1
R42 was flat. However, the control ran with much higher volatile R03/R44 time:
Grid-1 R03 was `1.600/0.847 s` and R44 was `5.251/2.924 s`. Those differences
are larger than the total-wall reduction and make the apparent `-3.82%` total
an invalid standalone speedup claim.

## Decision

Keep `12x8` as a promising 4n96 cumulative/final configuration candidate, not
as the new daily 4n64 reference. It produced a large, causal R39/R55/R49 gain,
but regressed R42/R54 and its total was confounded by R03/R44 plus execution
order. Scaling the stable target-region deltas by the current full/DEMO ratios
suggests this shape alone is unlikely to reach the 2350-second goal, so do not
spend a full run on the shape alone. Re-evaluate it in a same-allocation 4n96
confirmation after the next source-level cumulative candidate.
