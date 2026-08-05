# Batch tracer boundary-flux reductions

- Accepted anchor: `f5b0a3d`
- Reference run:
  `Local_Lab/runs/profile128/batch-boundary-flux-4n64-16ppn_20260805T121107Z_58978`
- Reference binary SHA-256:
  `1b1ee471fcd70915ab1e68899a0734dfa1e7cd8547780604b6d12259bb09981b`
- Reference PROFILE total: Grid 1 `116.698110 s`, Grid 2 `116.700280 s`;
  mean `116.699195 s`.
- Reference region 49 calls per rank: Grid 1 `201178`, Grid 2 `38202`.

## Falsifiable hypothesis

`step3d_t` extracts a boundary-flux slice for every tracer and vertical
level. The accepted implementation assembles each completed slice immediately,
although no `Tflux` element is consumed inside the tracer/level loop. With 34
levels and 15 tracers this leaves roughly 510 collective synchronization points
per active contact and timestep.

Extracting the same slices locally in the same order, then packing the complete
west/east/south/north `Tflux` arrays and applying one element-wise sum after the
loop preserves the data dependency and every physical calculation. Each
boundary element has one owning rank and zero on all other ranks, so batching
does not reorder additions among multiple nonzero contributors.

Expected 4n64-16ppn DEMO evidence:

- region 49 calls per rank fall by roughly another factor of the vertical-level
  and tracer count on the affected path;
- region 49 and total PROFILE wall improve without a new dominant MPI region;
- the model ends normally and all 26 comparisons remain bitwise identical;
- peak RSS remains comfortably within the node allocation despite a reusable
  packed buffer of several MiB per rank.

No equation, input, timestep, tracer selection, precision, interpolation,
masking, compiler setting, or profiling source is changed.

## Result

- Clean build: job `118629251`, PASS; candidate
  `Local_Lab/runs/validation/candidate_20260805T122446Z_21728`; binary SHA-256
  `a0507ac874de64221fcfeea7aeaaa565f8b496be5d24f858c7a741b8a425b323`.
- 4n64-16ppn DEMO: job `118629398`, PASS; run
  `Local_Lab/runs/profile128/batch-tracer-boundary-flux-4n64-16ppn_20260805T123120Z_12354`.
- Correctness: normal end; all 26 comparisons have `RMSE=0` and
  `max_abs=0`.
- PROFILE total mean: `116.699195 s` to `108.080020 s` (`-7.39%`).
  Slurm elapsed wall: `118.99 s` to `110.76 s` (`-6.92%`).
- Grid 1 region 49 calls per rank: `201178` to `28078` (`-86.04%`);
  wall mean: `26.622368 s` to `21.087661 s` (`-20.79%`).
- Grid 2 region 49 calls per rank: `38202` to `3005` (`-92.13%`);
  wall mean: `18.576998 s` to `13.260396 s` (`-28.62%`).
- Peak RSS: `810724 KiB` to `819148 KiB` (`+8424 KiB`, `+1.04%`).

Accepted: both the predicted synchronization-count reduction and total-wall
improvement are large, numerical output is bitwise identical, and the reusable
buffer has negligible memory cost relative to the node allocation.
