# Specialize the K-kl GLS recompute identity

- Accepted anchor: `d2d4fc66bcc2bb96835f525b1ad68bc450f191ad`.
- Reference run:
  `Local_Lab/runs/profile128/gls-kkl-positive-unit-power-4n64-16ppn_20260808T182648Z_48607`
  (job `118796342`, 4n64/16ppn, 8x8, 60/300; profile total
  `73.18 s`, all 26 comparisons bitwise zero).
- Target: Grid-1/2 R19 (`2.2122/5.7920 s` in the current reference).
- Guard regions: R09, R22, R35, R39, R44, R49, R54 and R55.

## Falsifiable hypothesis

The active K-kl configuration makes `gls_p=0`, `gls_m=1`, and `gls_n=1`,
which the routine already records in `Lmy25`. After limiting the turbulent
length scale, every wet interior level nevertheless recomputes GLS through
three runtime real powers: `cmu0**0 * tke**1 * Ls**1`. Under `Lmy25` this is
exactly `tke*Ls`; the generic expression remains unchanged for every other
closure.

This experiment touches only that high-call-count recompute statement. It
does not alter negative or fractional powers, the limiter, multiplication of
the two non-unit operands, equations, precision, grids, MPI, inputs,
profiling, or validation. Expected behavior is bitwise-identical output and
lower R19 on both grids. Any nonzero DEMO error triggers the independent
1-rank gate before possible acceptance; a tolerance failure or no useful R19
direction rejects the experiment.

## Result: accepted

- Clean PROFILE build: job `118797281`, candidate
  `Local_Lab/runs/validation/candidate_20260808T184545Z_11512`, binary
  SHA-256 `3b70eea949c4ec47672a054391618a85ebaffbb59f2cc5c689a0bdeb1792cd6b`.
- Score DEMO: job `118797618`, run
  `Local_Lab/runs/profile128/gls-kkl-recompute-unit-powers-4n64-16ppn_20260808T185203Z_3250`.
  It ended normally and all 26 variables had `RMSE=0` and `max_abs=0`.
- Target R19 changed from `2.2122/5.7920 s` to `1.9693/5.1489 s` on
  Grid 1/2 (`-10.98%/-11.10%`) with unchanged calls.
- Profile total was effectively unchanged at `73.18 s`. This run had slower
  unrelated regions, including R44 (`3.9391/1.5037 s` to
  `4.2127/1.7213 s`) and Grid-2 R09 (`5.5722 s` to `5.7522 s`). Other guards
  were similarly small/noisy: R22 `2.4816/7.3009 s`, R35
  `3.2654/9.3114 s`, R39 `0.4037/9.3066 s`, R49 `3.4337/3.3706 s`, R54
  Grid 2 `4.0741 s`, and R55 Grid 2 `5.2264 s`. The acceptance decision is
  based on the large, consistent target-region gain rather than total noise.
- Independent 1-rank gate: job `118797810`, candidate
  `Local_Lab/runs/validation/candidate_20260808T185545Z_29058`; it ended
  normally and passed all 13 variables (`RMSE` and `max_abs <= 1e-5`).
- Evidence bundle:
  `profile_bundle_logs/gls-kkl-recompute-unit-powers-4n64-16ppn_20260808T185203Z_profile_bundle.json`.

The hypothesis is accepted. Profiler-v2 was essential here: total wall alone
would have hidden an approximately 11% improvement in the intended compute
region on both grids.
