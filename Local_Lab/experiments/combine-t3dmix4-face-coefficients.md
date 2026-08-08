# Combine t3dmix4 face coefficients

Date: 2026-08-09

## Hypothesis

- Accepted parent: `c28c20c`.
- Target: Grid 1/2 region 27.
- Reference:
  `Local_Lab/runs/profile128/cache-t3dmix4-coefficients-4n64-16ppn_20260808T211002Z_63841`.
- The accepted cache still loads separate diffusion and thickness-sum arrays
  and multiplies them in every tracer/pass. Cache their product instead,
  reducing four 3D work arrays to two and removing one load and multiplication
  per face flux. The active mask is binary, so multiplying the combined
  coefficient by it produces the same zero or unchanged coefficient.
- Expected result: R27 decreases by 5--10%, calls stay fixed, and all 26
  comparison variables remain bitwise identical. No other stable compute
  region should regress materially.

## Result

- Local gate: 53 tests passed.
- PROFILE build: job `118803655`, candidate
  `Local_Lab/runs/validation/candidate_20260808T213323Z_23753`, report PASS;
  binary SHA-256
  `d6fc9fcb71f6386f032ac501d5d81d5ece015f76a57c03de597608d78b7be153`.
- 4n64 DEMO: job `118803796`, run
  `Local_Lab/runs/profile128/combine-t3dmix4-face-coefficients-4n64-16ppn_20260808T213949Z_52705`.
- Correctness: normal end, output/comparison PASS, all 26 variables had
  `RMSE=0` and `max_abs=0`.
- Target result:
  - Grid 1 R27: `0.9729853 -> 0.8658157 s` (`-11.01%`).
  - Grid 2 R27: `2.3967872 -> 2.2492806 s` (`-6.15%`).
  - Calls unchanged at `3904` and `19200`.
- Profile total: `71.65 -> 71.59 s`. Grid-1 R44 independently increased
  `2.8776 -> 4.0542 s`, masking most of the target reduction; stable compute
  regions R35, R39 and R54 also moved downward rather than showing an
  offsetting regression.
- Independent 1-rank validation: job `118803885`, candidate
  `Local_Lab/runs/validation/candidate_20260808T214445Z_25961`, Slurm
  COMPLETED with exit code 0. `validation_report.json` passed, all 26
  file/variable metrics had zero error, and the model ended normally.

## Decision

Accepted. The target-region improvement, bitwise DEMO, and independent
validation satisfy all applicable gates despite known R44 allocation noise.
