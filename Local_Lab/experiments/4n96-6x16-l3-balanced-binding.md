# 4n96 6x16 L3-balanced NUMA-row binding experiment

- Accepted repository anchor: `2716b91fdcc6f17042f1ead3938916fbcdca61ee`.
- Frozen model source: `e7e0ce1`.
- Preserved score binary SHA-256:
  `d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220`.
- Control: accepted `ppr:6:numa` row binding, `6x16`, 4 nodes, 96 ranks,
  24 ranks/node, 60/300 score PROFILE.

## Evidence and falsifiable hypothesis

Slurm topology probe job `118849965` proved that each eight-core NUMA domain
contains two independent four-core L3 domains: cores 0--3 share L3 0 and cores
4--7 share L3 1, repeated at offsets 8, 16 and 24.  The accepted Open MPI
`ppr:6:numa` mapping chooses the first six cores in each NUMA domain.  It thus
places four ranks on one L3 and two on the other.  Its ABBA evidence improved
overall time but regressed Grid-2 R09 by 8.2% and R40 by 7.2%.

Keep each complete six-rank I row inside one NUMA domain, but select three
cores from each L3: `0,1,2,4,5,6`, then the same pattern at offsets 8, 16 and
24.  Node/rank placement, NUMA ownership, binary, messages, arithmetic and
outputs remain unchanged; only core choice inside each NUMA domain changes.

The hypothesis predicts recovery of R09/R40 without losing the accepted
R39/R41/R42/R49/R54 gains.  Test accepted/candidate/candidate/accepted in one
exclusive allocation with exact mapping probes.  Reject on any nonzero output
error, mapping mismatch, inconsistent target direction, or offsetting total.

## Result

ABBA job `118850078` ran on `j01r2n[06-09]`.  Both 96-rank mapping probes
matched exactly.  All four model runs ended normally and passed all 26 output
comparisons with `RMSE == 0` and `max_abs == 0`.

Resource walls in accepted/candidate/candidate/accepted order were
`104.33/102.11/103.03/103.36 s`.  Means changed `103.845 -> 102.570 s`, a
repeatable `1.275 s` (`1.23%`) improvement.  Grid-2 PROFILE R0 means changed
`101.667 -> 100.018 s` (`-1.62%`).  Calls were identical.  Selected ABBA-mean
changes were R09 `-1.0%`, R35 `-1.4%`, R40 `-2.3%`, R41 `-9.0%`, R49
`-1.1%`, and R54 `-0.9%`; R22 was neutral (`+0.5%`), while R42 and R55
regressed `3.5%` and `1.1%` respectively.  R39 was neutral (`+0.3%`).

Decision: accept the L3-balanced core list as the refined production binding.
Both candidates beat both controls, total and the intended R09/R40 guards
improved, and the small R42/R55 trade-off did not offset the gain.  Combining
the two independently paired binding ratios with the validated `2461.22 s`
full result projects about `2361 s`; this is not a full-run claim and remains
roughly 11 seconds above the `2350 s` target.  Retain the binding for the next
cumulative full candidate after one more narrow, independently gated gain.
