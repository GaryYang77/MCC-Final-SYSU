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
`d1a7f5e3e27a0e11084451543410f89121bb2dcc905cc5772425e7b073cc67da`.

This ComputeImproved binary was built from source commit
`7e3b9893b7356469df387359c98bd887bc43dd73`.  Its complete 4-node/96-rank
run (job `119050104`) finished in `35:47.77`; official validation job
`119053745` passed all variables for both grids with reported RMSE `0.000000`.
