# R44 broadcast region is dominated by output I/O wait

Observation date: 2026-08-07, after the direct-pack/sparse-peer contact
commits (`dbe0535`, `8196341`).

## Evidence

The 4n64-16ppn DEMO writes the AVERAGE files every outer step
(`NAVG == 60 300` in the runner-generated `ocean_profile.in`).  The
produced files contain 172 variables (SCS) and 164 variables (Dongsha60),
and every write call performs:

1. `OutThread`: `nf90_put_var` (the actual file write), then
2. all ranks: `mp_bcasti(ng, model, status)`.

See `nf_fwrite2d.F` / `nf_fwrite3d.F`.  Non-I/O ranks therefore spend the
whole per-variable wait (write + broadcast) inside profile region 44
(`mpi_broadcast`).

Across otherwise identical accepted runs, Grid 1 region 44 measured
`3.35 / 4.05 / 4.86 / 5.24 s` and Grid 2 measured `1.53 / 1.82 / 1.90 /
2.42 s`.  This run-to-run spread (±1 s on the total) is much larger than
the targeted gains of the F2C experiments and explains why those single
DEMO runs showed total regressions while their target regions improved.

## Consequence

Do not spend effort batching the per-write status broadcasts: the wait is
dominated by the file write on the I/O thread, so moving the broadcast
does not reduce total wall.  The variance is filesystem/network
contention and is outside the source code.

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
