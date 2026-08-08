# Specialize positive unit GLS powers for K-kl

- Accepted anchor: `ed04ce3fefa9c4d27bf7e7cf89e28c1b51684641`.
- Reference run:
  `Local_Lab/runs/profile128/cache-predictor-time-metric-4n64-16ppn_20260808T173126Z_64643`
  (job `118793509`, 4n64/16ppn, 8x8, 60/300; profile total
  `74.70 s`, all 26 comparisons bitwise zero).
- Target: Grid-1/2 R19 (`2.487/6.468 s` in the current reference).
- Guard regions: R09, R22, R35, R39, R49, R54 and R55.

## Falsifiable hypothesis

The active input selects K-kl with exactly `GLS_P=0`, `GLS_M=1`, and
`GLS_N=1`; `gls_corstep` already detects this as `Lmy25`. The Intel 17
optimization report shows that general `pow` calls inhibit vectorization in
the hot water-column loops. A previous broad K-kl specialization reduced R19
by about 56% but failed the numerical gate because it also rewrote reciprocal
and fractional powers and reused other algebra.

This narrow experiment removes only two positive unit powers. Inside the
existing `Lmy25` wall branch, `gls**gls_exp1` becomes the same `gls` value;
the later length-scale calculation selects that identity only when `Lmy25` is
true and retains the original general-power expression otherwise. Negative
TKE powers, fractional powers, multiplication order, equations, precision,
bounds, MPI, inputs, profiling and validation are unchanged.

The expected output is bitwise identical if the runtime positive-unit `pow`
returns its operand exactly. Any nonzero DEMO error is treated as numerical
risk and triggers the independent 1-rank gate before possible acceptance;
tolerance failure rejects immediately. Expected performance is materially
lower R19 on both grids with unchanged calls and neutral guards. No useful
R19 direction also falsifies the hypothesis.

## Result: accepted

- Clean PROFILE build: job `118795951`, candidate
  `Local_Lab/runs/validation/candidate_20260808T181941Z_20335`, binary
  SHA-256 `2e5cfef07ddf371b3cd7bad5a7023f29e37d438bfccd31c859d0e34581ddc362`.
- Score DEMO: job `118796342`, run
  `Local_Lab/runs/profile128/gls-kkl-positive-unit-power-4n64-16ppn_20260808T182648Z_48607`.
  It ended normally and all 26 variables had `RMSE=0` and `max_abs=0`.
- Profile total changed from `74.70 s` to `73.18 s` (`-2.03%`). More
  importantly, the targeted R19 changed from `2.4870/6.4680 s` to
  `2.2122/5.7920 s` on Grid 1/2 (`-11.05%/-10.45%`) with unchanged calls.
- Guard regions were directionally neutral apart from ordinary communication
  noise: R22 was `2.4782/7.2779 s`, R35 `3.2479/9.2336 s`, R39
  `0.3983/9.2364 s`, R49 `3.3432/3.3493 s`, R54 Grid 2 `4.0433 s`, and R55
  Grid 2 `5.1870 s`. R44 varied from `4.0915/1.7591 s` to
  `3.9391/1.5037 s`, so total wall is not attributed solely to this change.
- Because the change specializes arithmetic, the independent 1-rank gate was
  run despite the bitwise DEMO: job `118796457`, candidate
  `Local_Lab/runs/validation/candidate_20260808T183032Z_9495`; it passed all
  13 variables (`RMSE` and `max_abs <= 1e-5`) and ended normally.
- Evidence bundle:
  `profile_bundle_logs/gls-kkl-positive-unit-power-4n64-16ppn_20260808T182648Z_profile_bundle.json`.

The hypothesis is accepted: removing only the two positive unit powers avoids
some costly general `pow` work without reproducing the numerical failure of
the earlier broad K-kl specialization.
