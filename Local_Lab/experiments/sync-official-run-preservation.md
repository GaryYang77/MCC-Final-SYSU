# Official-run preservation incident

## What happened

On 2026-08-11, `Local_Lab/sync_to_cluster.sh` was used to deploy the R35
diagnostic sources.  The script intentionally uses `rsync --delete` and
already protected `Local_Lab/runs`, builds, baselines, and cluster logs, but it
did not protect the newer `sysu_official_launch/run_*` result directories.
Rsync could not delete the non-empty `output/` directory, so all 16 NetCDF
outputs from official job `118919233` survived, but it removed peripheral
files that existed only on the server.

The original `model.log`, `resource.log`, and Slurm stdout/stderr text cannot
be recovered and must not be reconstructed or represented as originals.

## Recovery evidence

- All 16 original NetCDF output files remain in
  `sysu_official_launch/run_118919233/output/`.
- The launch binary was restored from the unchanged
  `sysu_official_launch/oceanM`; its SHA-256 in the run directory is
  `1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410`.
- `ocean.in`, the rankfile, and required input links were regenerated from the
  unchanged official-launch configuration.
- Slurm accounting was preserved in `slurm_accounting.txt`:
  job `118919233`, `COMPLETED`, elapsed `00:37:16`, raw elapsed `2236 s`, nodes
  `j05r2n[01-04]`, exit code `0:0`.
- The official validator was copied again, with only `dir_test` changed, and
  rerun against the surviving output.  Both grids and every variable passed;
  the final official result was “优化结果无异常”.

This recovery preserves the scientific outputs and independently verifiable
completion/correctness evidence.  It does not claim to restore the lost text
logs.

## Prevention

`sync_to_cluster.sh` now excludes all of the following before its broad
`--delete` operation:

- `/sysu_official_launch/run_*/`
- `/sysu_official_launch/slurm_*.out`
- `/sysu_official_launch/slurm_*.err`

A static regression test requires these exclusions.  Model/profiler source
deployment during an active experiment should still prefer explicit file
uploads when a full repository sync is unnecessary.
