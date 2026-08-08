# Cache C4 tracer transport half-planes

- Accepted anchor: `162ad2cac1534e55848f1ae0a28f873a0fb479bf`.
- Reference run:
  `Local_Lab/runs/profile128/gls-kkl-recompute-unit-powers-4n64-16ppn_20260808T185203Z_3250`
  (job `118797618`, 4n64/16ppn, 8x8, 60/300; profile total
  `73.18 s`, all 26 comparisons bitwise zero).
- Current phase no-profile measurement: `75.53 s` in paired job `118798959`.
- Target: Grid-1/2 R35 (`3.2654/9.3114 s`), specifically profiler-v2 site
  132 horizontal tracer advection.
- Guard regions: R09, R19, R22, R39, R44, R49, R54 and R55.

## Falsifiable hypothesis

The application defines `TS_U3ADV_SPLIT`, but `globaldefs.h` implements this
by enabling `TS_C4HADVECTION` and `TS_DIF4`. In the actual C4 horizontal
advection flux, every tracer at a fixed vertical level repeats the identical
`Huon*0.5` and `Hvom*0.5` products. With 15 tracers, compute those two 2D
half-transport planes once per level and reuse them.

For each output, the original left-associated expression is
`(transport*0.5)*parenthesized_flux`; the candidate stores exactly the first
product and performs the same second multiplication. Gradient, curvature,
tracer arithmetic, operation order, loop bounds, equations, precision,
masks, MPI, inputs, profiling and validation are unchanged. Two tile-local
2D work arrays replace repeated products.

The clean candidate SHA must differ from the accepted binary, proving the
path is active. Expected output is bitwise identical. Expected performance is
lower R35 on both grids with unchanged calls and neutral guards. Any identical
SHA, nonzero comparison, stack/runtime failure, or no useful R35 direction
rejects the experiment.

## Result: accepted

- Clean PROFILE build: job `118801327`, candidate
  `Local_Lab/runs/validation/candidate_20260808T195741Z_20169`, binary
  SHA-256 `2fb6b838415fbfc83f9477932e44ce5b1b004f4a48d0b64ad9fed57e8a419fbc`.
  The hash differs from the accepted binary, confirming the C4 path is active.
- Score DEMO: job `118801701`, run
  `Local_Lab/runs/profile128/cache-c4-transport-halves-4n64-16ppn_20260808T200411Z_51013`.
  It ended normally and all 26 variables had `RMSE=0` and `max_abs=0`.
- Target R35 changed from `3.2654/9.3114 s` to `3.2210/9.1713 s` on
  Grid 1/2 (`-1.36%/-1.50%`) with unchanged calls.
- Profile total changed from `73.18 s` to `72.41 s` (`-1.05%`). Guards were
  neutral or faster apart from ordinary noise: R09 `1.8589/5.5273 s`, R19
  `1.9325/5.0694 s`, R22 `2.4823/7.2790 s`, R39 `0.3989/9.2363 s`, R49
  `3.3229/3.3387 s`, R54 Grid 2 `4.0306 s`, and R55 Grid 2 `5.1997 s`.
  Grid-1 R44 moved slightly from `4.2127` to `4.2527 s` while Grid-2 R44
  improved, consistent with its known volatility.
- Evidence bundle:
  `profile_bundle_logs/cache-c4-transport-halves-4n64-16ppn_20260808T200411Z_profile_bundle.json`.

Decision: accept. The implementation preserves output bits and produces the
predicted R35 reduction on both grids, while the end-to-end score moves in the
same direction.
