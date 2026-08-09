# In-place 1D assembly cumulative full validation

- Accepted commit: `1ba85ab2149598702c6011e12940612a0a21119c`.
- Configuration: 4 nodes, 96 ranks, 24 ranks/node, `6x16`, L3-balanced
  NUMA-row binding, complete 2592/12960 steps.
- No-profile build: job `118852333`,
  `Local_Lab/builds/profiling/no_profile_20260809T223846Z_25681/bin/oceanM`.
- Binary SHA-256:
  `1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410`.
- Triggered independent validation: job `118852320`, candidate
  `Local_Lab/runs/validation/candidate_20260809T223816Z_17316`, PASS.

## Warrant

The daily score gate for commit `1ba85ab` reduced R49 by `28.53%/6.77%` on
Grid 1/2 with unchanged calls and bitwise-identical output.  R49 carries much
more weight in the complete 4n96 workload, so this accepted cumulative source
is warranted for a real no-profile full run.

The existing launcher is reused with explicit environment overrides for the
exact binary and SHA.  It proves the L3 mapping, runs a same-allocation 60/300
no-profile preflight with a 90-second slow-node cutoff, preserves full output
cadence, compares all 26 variables, and runs the official validator with only
its `dir_test` line changed.

## Result

Goal achieved.

- Slurm job: `118852631`, nodes `j05r2n[04-07]`.
- Same-allocation preflight: `64.00 s`, normal end and comparison PASS.
- Complete three-day no-profile wall: **`2205.57 s`** (`36:45.57`).
- Exact full run:
  `Local_Lab/runs/profile128/final-6x16-l3-full-noprofile-20260809T225144Z_20260809T225150Z_41657`.
- `full_run_report.json`: `passed=true`.
- `run_report.json`: `passed=true`, `normal_end=true`, outputs and comparison
  PASS; all 26 variables have `RMSE=0` and `max_abs=0`.
- Official `vali.py`: both files and every reported variable have zero RMSE;
  the required final Chinese PASS verdict is present in `vali_official.log`.

This is `220.42 s` (`9.09%`) faster than the preceding L3-balanced complete
result (`2425.99 s`), `255.65 s` (`10.39%`) faster than the initial validated
`6x16` result (`2461.22 s`), and `294.17 s` (`11.77%`) faster than the earlier
`8x12` result (`2499.74 s`).  It beats the `2350 s` objective by `144.43 s`
(`6.15%` margin), satisfying the optimization goal with exact output and
official validation.
