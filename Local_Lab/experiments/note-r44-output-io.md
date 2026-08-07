# R44 broadcast region is dominated by output I/O wait

Observation date: 2026-08-07, after the direct-pack/sparse-peer contact
commits (`dbe0535`, `8196341`).

## Evidence

The 4n64-16ppn DEMO writes each AVERAGE file exactly once (60/300 steps,
`NAVG == 60 300`, one record per file), so output I/O contributes only a
few hundred of the 340480 Grid-1 region-44 calls.  The dominant R44
traffic is the per-outer-step distribution of forcing/data fields:
`nf_fread2d`/`nf_fread3d` and the boundary readers perform two broadcasts
per read (a small status/attribute buffer, then the full data array
`mp_bcastf(A)`), and the DEMO reads roughly 40-90 such fields per outer
step on the 60-step path.

Across otherwise identical accepted runs, Grid 1 region 44 measured
`3.35 / 4.05 / 4.86 / 5.24 s` and Grid 2 measured `1.53 / 1.82 / 1.90 /
2.42 s`.  This run-to-run spread (±1 s on the total) is much larger than
the targeted gains of the F2C experiments and explains why those single
DEMO runs showed total regressions while their target regions improved.

## Consequence

Do not spend effort on compact AVERAGE output for the DEMO KPI: the file
has a single record, so skipping later records has no measurable effect
(the full three-day runs write only ~3-4 AVERAGE records per grid as
well).  The real R44 lever is the full-field read broadcast: the accepted
`scatterv-input-fields` work replaced the initial-input broadcast with a
per-rank `MPI_Scatterv`, but the per-step forcing path still broadcasts
every field to every rank.  Extending the scatter distribution to that
path is the largest remaining R44 opportunity (~2-4 s on the DEMO plus
contention sensitivity).

## Measurement implications

- Small (<1 s) source-level gains cannot be separated from R44 noise by a
  single DEMO run.  The F2C sparse-peer and F2C direct-pack candidates
  (archived under `/tmp/sparse-peer-f2c-failed/` and
  `/tmp/f2c-direct-pack-failed/`, runs still on the cluster) improved
  Grid 2 R39/R55 by ~0.2-0.3 s with bitwise-identical output but failed
  the single-run total gate.  A team decision on paired reruns is needed
  before committing either.
- Future experiments should prefer stable regions (compute kernels,
  nesting R39/R55, halo exchanges) over regions containing output I/O, or
  should be evaluated with repeated runs when the targeted gain is small.

## 2026-08-07 addendum: advection loop-fusion experiment failed

`perf/fuse-advection-grad` fused the two-pass 4th-order centered advection
difference computation (`FX` row + edge fixes + `grad` row, and the
`FE/grad` Y-direction counterpart) in `pre_step3d.F` and `step3d_t.F`.
Debugging found a real edge-case trap: for the northernmost tile
`Jendp2 = MIN(Jend+2, Mm+1)` is clamped, so a fused Y loop can never reach
`j=Jend+2`; the north-edge fix and `grad(i,Jend+1)` must be applied after
the loop (the accepted two-pass form does this implicitly).  The composite
boundary grid (Dongsha60) hid the bug because its north fix is skipped.
With the fix, the DEMO was bitwise identical, but Grid 2 R22/R35 became
~1.5-2% slower (`8.269 -> 8.391 s`, `9.367 -> 9.542 s`) and the total
regressed `76.450 -> 77.264 s`; the candidate was reverted and archived
under `/tmp/fuse-advection-grad-failed/`.  Loop fusion of these small
L1-resident rows does not pay on this compiler/hardware.
