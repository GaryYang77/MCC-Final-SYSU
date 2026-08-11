# SYSU official launch

From the repository root on the cluster:

```bash
sbatch --wait sysu_official_launch/sub.sh
```

The script runs the complete 4-node/96-rank simulation and then compares
`SCS_avg_0001.nc` and `Dongsha60_avg_0001.nc` against the official files using
an unmodified copy of `/public/share/mcc2026_final/vali.py` except for its
`dir_test` line.  Results are written under
`sysu_official_launch/run_<job-id>/`.

The required `sysu_official_launch/oceanM` must have SHA-256
`1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410`.
