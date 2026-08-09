# Specialize K-kl boundary and boundary-flux powers

Date: 2026-08-09

## Hypothesis

- Accepted parent: `2c3d9b6f014f11aaa5b51558a2719edcb2c2cba8`.
- Reference:
  `Local_Lab/runs/profile128/batch-step2d-zeta-halos-4n64-16ppn_20260809T000452Z_12870`.
- Target: Grid 1/2 R19 (`gls_vertical_mixing`).
- The active K-kl closure is already detected by `Lmy25` and has exactly
  `GLS_P=0`, `GLS_M=1`, `GLS_N=1`. Prior accepted work specialized two
  positive unit powers and the interior GLS recompute, but surface/bottom GLS
  conditions and their boundary fluxes still evaluate multiple per-cell
  runtime powers with exponents zero or one.
- Under `Lmy25`, replace only those positive-base `x**0` and `x**1` calls by
  `1.0_r8` and `x`, retaining the original multiplication order and explicit
  identity factors. The generic closure path is byte-for-byte present.
- No negative/fractional powers, limiter, equation, coefficient, bounds,
  precision, MPI, input or profiler code changes.
- Expected output is bitwise identical and R19 falls by 3--7% on both grids
  with unchanged calls and neutral stable guard regions. Any nonzero output,
  no useful R19 direction, or guard regression rejects the candidate.

## Result

- Clean PROFILE build job `118807602`; candidate
  `Local_Lab/runs/validation/candidate_20260809T005202Z_28901`; binary
  SHA-256 `98e6c7954f86cb361e35ef8372aabb473f8589460a9d0684d2e80f97c3077c2f`.
- 4n64 DEMO job `118807778`; run
  `Local_Lab/runs/profile128/gls-kkl-boundary-powers-4n64-16ppn_20260809T005828Z_6875`.
- Normal end and every output/comparison gate passed; all 26 variables were
  bitwise identical.
- With unchanged calls, R19 fell `2.02930 -> 1.93183 s` on Grid 1
  (`-4.80%`) and `5.26000 -> 5.10351 s` on Grid 2 (`-2.98%`). Grid 2 is
  just below the predicted 3% lower bound but the two-grid causal direction is
  clear.
- Stable compute and nesting guards were neutral or faster apart from tiny
  noise. Total changed `71.10 -> 71.70 s` because volatile R44 rose
  `3.808/1.484 -> 4.535/1.724 s`; that I/O waiting increase is unrelated to
  this compute-only change.
- Independent validate job `118807823` passed. Its clean candidate was
  `Local_Lab/runs/validation/candidate_20260809T010147Z_11890`; the validation
  report passed with all checked errors within `1e-5`.

## Decision

Accept after the triggered independent validate. The intended pure-compute
region improved consistently on both grids with exact DEMO output; total wall
is contradicted only by the already characterized R44 allocation noise.
