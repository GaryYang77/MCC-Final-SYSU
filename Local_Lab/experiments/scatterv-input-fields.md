# Scatter only each rank's input-field tile

- Accepted anchor: `270e69ada7417711a1cd8aefa949ebcb4b211adc`
- Reference run: `Local_Lab/runs/profile128/sparse-contact-allgatherv-2n64_20260804T140306Z_26445`
- Reference binary SHA-256: `cca7aad0237cc6c8e7c841e5c55d46444c9b8c7e526564c6136066389a933753`
- Reference wall: `211.57 s`
- Target: Grid 1 region 47 (`mpi_data_scattering`), `44.9693 s` with 4608
  aggregate calls; Grid 2 region 47 is only `1.0224 s`.

## Falsifiable hypothesis

`mp_scatter2d` and `mp_scatter3d` currently broadcast the complete global
input field to all ranks, allocate/zero another full-grid receive array on
every rank, and then copy only the local tile.  For the competition's one-rank
per-tile decomposition, the master can pack each rank's requested rectangular
tile (including the same requested ghost range) and use `MPI_Scatterv`, so each
rank receives only the values it writes to `Awrk`.

Expected DEMO evidence:

- region 47 call count remains unchanged but Grid 1 region 47 wall decreases;
- total wall decreases without moving work into another MPI region;
- non-master full-grid temporary storage is removed or reduced, lowering RSS;
- local unpack order and values are bitwise identical, including `Amin/Amax`,
  staggered C-grid offsets, vertical order, masks, and requested ghost ranges;
- configurations that do not have one rank per tile retain the current
  broadcast implementation.

This changes only distribution of already-read input fields.  NetCDF reads,
input data, physical equations, time steps, and profiling instrumentation are
unchanged.

## Accepted result

- Validation: job `118559799`, candidate
  `candidate_20260804T141805Z_22911`, binary SHA-256
  `4aeccdcce76f414e19e3dfa05fc3a8ed6529278bde93498bd6547b4ba2d8c8dc`;
  exit 0, `[validate] PASS`, report `passed=true`.
- DEMO: job `118560345`, run
  `scatterv-input-fields-2n64_20260804T142758Z_12148`; `passed=true`,
  `normal_end=true`, `comparison.passed=true`, with all 26 entries at zero
  RMSE and zero max-absolute error.
- Resource wall decreased from `211.57 s` to `162.99 s`, a `48.58 s`
  (`22.96%`) improvement.
- Grid 1 region 47 decreased from `44.969264 s` to `0.840850 s`
  (`98.1%`), with unchanged aggregate calls (`4608`).  Grid 2 region 47
  decreased from `1.022449 s` to `0.214463 s`.
- Maximum RSS decreased from `825492 KiB` to `806560 KiB` (`2.3%`), system
  CPU time from `259.78 s` to `203.78 s`, and user CPU time from `6143.13 s`
  to `4897.76 s`.
- Relative to the original accepted daily baseline `283.07 s`, the cumulative
  DEMO wall is now `42.42%` lower.  Reaching the `50%` target (`141.535 s`)
  requires another `21.46 s`.

Accepted: the target region and total wall both improve decisively, memory use
falls, and numerical output remains bitwise identical.
