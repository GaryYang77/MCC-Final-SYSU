# 4n96 6x16 NUMA-row rank-binding experiment

- Accepted repository anchor: `8c0749505c28f567aab2663dd318f121c2f6a8ac`.
- Frozen model-source anchor: `e7e0ce1`.
- Preserved score binary SHA-256:
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- Reference: default Open MPI binding, 4 nodes, 96 ranks, 24 ranks/node,
  `6x16`, 60/300 steps,
  `Local_Lab/runs/profile128/tile-shape-candidate-6x16-4n96_20260809T183013Z_39381`.

## Evidence and falsifiable hypothesis

Slurm hardware probe job `118846871` showed four eight-core NUMA domains per
32-core Hygon C86 node.  Default Open MPI binding probe job `118849318` spreads
successive ranks across cores `0,8,16,24,1,9,...`.  It balances six ranks per
NUMA domain, but for I-fastest `6x16` decomposition the six ranks in each tile
row are split across all four NUMA domains, so almost every east/west node-local
halo edge crosses a NUMA boundary.

Probe jobs `118849373` (CLI) and `118849400` (MCA environment) verified a
different mapping: `ppr:6:numa`, slot ranking and core binding place ranks
0--5 on cores 0--5, ranks 6--11 on cores 8--13, and so on.  Each complete
six-rank I row then resides inside one NUMA domain while every domain still
owns exactly six ranks.  Node/rank order, model arithmetic, binary, messages,
precision and outputs are unchanged.

The hypothesis predicts lower Grid-2 R40/R41/R42 and possibly R39/R49/R55
with unchanged call counts and neutral compute regions.  It is falsified if
stable communication regions and total do not improve materially over the
same `6x16` binary.  Volatile R03/R44 changes cannot justify acceptance.  A
full no-profile run is warranted only if score evidence can plausibly close
the remaining 111.22-second (`4.73%`) gap to 2350 seconds.

The standard launcher inherits these verified MCA settings through its
existing `--export=ALL` behavior:

```
OMPI_MCA_rmaps_base_mapping_policy=ppr:6:numa:PE=1
OMPI_MCA_rmaps_base_ranking_policy=slot
OMPI_MCA_hwloc_base_binding_policy=core
```

## Result

The first candidate-only score job `118849431` passed all 26 comparisons with
bitwise-zero error, but ran on `j01r2n[06-09]` and reported `101.68 s` versus
the reference's `67.09 s`.  Compute-only regions also regressed sharply (R35
`9.73 -> 16.80 s`, R09 `5.05 -> 11.98 s`), which cannot be caused by the
communication-locality mechanism alone and matches the repository's known
large node-group effect.  This cross-allocation run is therefore insufficient
to accept or reject the binding.  Run default/bound/bound/default in one
exclusive allocation before deciding.

The first ABBA launcher submission, job `118849650`, exited before mapping
probes or model execution because the compute-node Bash lacks `local -n`
nameref support.  The runner was changed to an ordinary conditional array
lookup; this infrastructure failure contains no performance evidence.

The corrected ABBA job `118849753` ran on `j01r2n[10-13]`.  Both mapping
probes matched all 96 expected rank/node/core triples.  All four model runs
ended normally, produced complete profile reports, and passed all 26
comparisons with `RMSE == 0` and `max_abs == 0`.

Resource walls in control/bound/bound/control order were
`109.06/106.60/104.64/108.47 s`.  The control mean was `108.765 s` and the
NUMA-bound mean `105.620 s`, a repeatable `3.145 s` (`2.89%`) improvement.
Grid-2 PROFILE R0 means changed `106.542 -> 103.172 s` (`-3.16%`).  Selected
ABBA-mean region changes, with identical calls, were:

| Region | Control mean | NUMA-bound mean | Change |
| --- | ---: | ---: | ---: |
| R09 2-D kernel | 9.569 s | 10.349 s | +8.2% |
| R22 predictor | 7.354 s | 6.857 s | -6.8% |
| R35 tracer corrector | 18.266 s | 17.130 s | -6.2% |
| R39 nesting | 19.073 s | 17.875 s | -6.3% |
| R40 2-D halo | 11.243 s | 12.048 s | +7.2% |
| R41 3-D halo | 7.542 s | 6.721 s | -10.9% |
| R42 4-D halo | 10.097 s | 8.254 s | -18.2% |
| R49 point gathering | 8.572 s | 7.810 s | -8.9% |
| R54 put receiver data | 8.437 s | 7.531 s | -10.7% |
| R55 two-way coupling | 10.630 s | 10.337 s | -2.7% |

Decision: accept the NUMA-row mapping as the production binding for `6x16`.
The repeated R39/R41/R42/R49/R54 reductions and total agree with the locality
mechanism despite the R09/R40 trade-off.  Do not run another full simulation
for this change alone: applying the measured `2.89%` to the validated
`2461.22 s` result projects about `2390 s`, still above the `2350 s` target.
Retain it for a cumulative candidate after another independently gated source
or configuration gain.
