# 4n96 12x8 I-stripe rank-placement experiment

- Repository anchor: `c4801847934ea08f03a18e69032e5c6eea05db3d`.
- Frozen model-source anchor: `e7e0ce1` (`perf(biology): hoist shallow-water light factor`).
- Preserved score binary SHA-256:
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- Configuration: 4 nodes, 96 ranks, 24 ranks/node, `12x8` tiles,
  60/300 steps, score PROFILE.
- Accepted output reference:
  `Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482`.

## Evidence and falsifiable hypothesis

The same-allocation full run in job `118834493` established that `12x8` is
numerically valid but not yet faster than `8x12`: no-profile wall was
`2533.55 s` versus the prior `2499.74 s`. Both full no-profile and PROFILE
runs ended normally, had 26 bitwise-identical variables, and passed official
`vali.py`.

The full PROFILE comparison nevertheless shows a real nesting advantage on
Grid 2: R39 changed `538.353 -> 463.537 s`, R49 changed
`249.583 -> 154.947 s`, and R55 changed `352.455 -> 253.829 s`. This was
offset by regressions including R22 `240.199 -> 282.296 s`, R35
`410.858 -> 433.507 s`, and R42 `234.093 -> 270.793 s`.

ROMS maps tile ranks with I varying fastest. With the default contiguous rank
placement, every 24-rank node owns two complete 12-wide J rows, so the three
node cuts cross 36 nearest-neighbour tile edges. Assigning each node three
complete I columns instead crosses 24 edges. The hypothesis is that this
I-stripe rank-to-node mapping reduces remote halo/nesting traffic while
retaining the `12x8` R39/R49/R55 geometry benefit.

This is a pure placement experiment. The binary, rank count, tiles, input,
steps, physics, arithmetic, profiling definitions, and validation are
unchanged. Control and candidate must use the same explicit CPU-binding policy
and run in ABBA order within one exclusive allocation. A pre-model mapping
probe must prove 24 ranks on each of four nodes, the requested rank-to-node
mapping, and equivalent per-node CPU-binding distributions.

Topology probe job `118836961` ran on four allocated compute nodes and
confirmed 32 single-thread cores, one socket, and four NUMA nodes per node.
The explicit 24ppn control maps each node's 24 local ranks to logical cores
`0..23`; the candidate rankfile preserves exactly that core set and changes
only which global ranks occupy the four nodes.

## Gate and decision

All four runs must end normally, produce complete outputs and profile reports,
and pass the 26-variable comparison. Calls must remain unchanged. The primary
targets are Grid-2 R39/R49 and the R54/R55 nesting children; R40/R41/R42 are
communication guards, R35/R22 are compute guards, and R03/R44 are reported as
volatile regions.

Accept the mapping for a production comparison only if both mapped runs show
a repeatable target-path reduction relative to the two controls without an
offsetting total or stable-compute regression. Reject immediately if the
mapping/binding probe fails, any numerical error is nonzero, either target
moves inconsistently, or the gain is too small to justify a follow-up full
run. A short placement result alone is not a final speedup claim.

## First implementation result: rejected

Job `118837122` ran control/mapped/mapped/control on `j04r2n[00-03]`. All four
runs ended normally and all 26 comparisons were bitwise identical. Exact run
directories are recorded in
`rank-map-i-stripe-a-20260809T162106Z_20260809T162117Z_50906/rank_map_abba_report.json`.

The explicit `ppr:24:node --bind-to core` control bound local ranks to cores
`0..23`. This was a non-production binding: controls took `112.20/123.00 s`,
far slower than the unqualified `mpirun` configuration. Even within that
matched binding, the candidate was repeatably unhelpful: mapped runs took
`114.78/115.73 s`, and mean PROFILE total increased `2.1%`.

Selected Grid-2 mean changes, averaging each ABBA pair, were R39 `-1.1%`,
R42 `-11.6%`, and R54 `-9.3%`, but R40 regressed `27.5%`, R49 regressed
`5.6%`, R55 regressed `6.7%`, and R35 regressed `3.6%`. The intended
R39/R49/R55 mechanism was therefore falsified for this implementation.

Decision: reject the `core 0..23` mapping and binding. The initial topology
probe used explicit mapping flags and therefore did not establish the binding
order of the production command, which uses unqualified `mpirun -np 96`.
Probe that exact command before deciding whether one corrected rankfile test is
warranted; do not reuse this launcher as a candidate.

Default-command probe job `118837638` then established the actual production
binding sequence on each node as
`0,8,16,24,1,9,17,25,...,5,13,21,29`, round-robin across the four NUMA
domains. The corrected implementation keeps the control command exactly
`mpirun -np 96` and assigns that same ordered 24-core set to every node in the
candidate rankfile. One corrected ABBA is warranted because it isolates the
original rank-to-node hypothesis without the rejected NUMA-binding change.

## Corrected implementation result: accepted for 12x8 production comparison

Job `118837733` ran on `i17r1n[04-07]` with exact production binding preserved.
The control/mapped/mapped/control resource walls were
`70.06/67.04/67.14/68.01 s`. Thus the two-control mean was `69.04 s` and the
two-candidate mean was `67.09 s`, a repeatable `2.82%` reduction. Grid-2
PROFILE R0 means changed `66.617 -> 65.019 s` (`-2.40%`). Exact run
directories and walls are recorded in
`rank-map-i-stripe-a-20260809T163618Z_20260809T163625Z_60140/rank_map_abba_report.json`.

All four mapping/core probes matched exactly. All four model runs ended
normally, produced complete outputs and reports, and passed the 26-variable
comparison with `RMSE=0` and `max_abs=0`. Region calls were identical. Selected
Grid-2 ABBA-mean changes were:

| Region | Control mean | I-stripe mean | Change |
| --- | ---: | ---: | ---: |
| R35 tracer corrector | 10.105 s | 9.922 s | -1.8% |
| R39 multiple-grid nesting | 10.865 s | 10.606 s | -2.4% |
| R40 2-D halo | 2.692 s | 2.696 s | +0.1% |
| R41 3-D halo | 2.137 s | 2.142 s | +0.2% |
| R42 4-D halo | 6.304 s | 5.838 s | -7.4% |
| R49 point gathering | 3.816 s | 3.674 s | -3.7% |
| R54 put receiver data | 4.858 s | 4.701 s | -3.2% |
| R55 two-way coupling | 6.000 s | 5.899 s | -1.7% |

Decision: accept the corrected I-stripe mapping as the `12x8` placement for a
future cumulative full candidate. Do not run a full simulation for this change
alone: its measured 2-3% gain is insufficient to take the existing `2533.55 s`
12x8 no-profile result below `2350 s`. This 4n96 result also does not satisfy
the repository's 4n64/8x8 DEMO target; source optimization remains necessary.
