# Batch four directional boundary-flux reductions

- Accepted anchor: `91b151f7b97bb872633101d509d6f1dc20e3b57b`
- Performance source anchor: `d31f6237f832df1c7d3c5ae7c01bcbff6cc71cb9`
- Reference run: `Local_Lab/runs/profile128/ipo-compiler-4n64-16ppn_20260805T060817Z_56689`
- Reference binary SHA-256: `eb230829ec04adfa6f886c3104ded45bc65880dce0710bc625e405c33254aac0`
- Reference PROFILE total: Grid 1 `117.743620 s`, Grid 2 `117.745570 s`
- Target: Grid 1 region 49 `29.923821 s` and Grid 2 region 49
  `15.671707 s`.

## Falsifiable hypothesis

Three hot refinement paths (`bry_fluxes`, `check_massflux`, and
`put_refine2d`) reduce west, east, south, and north boundary-flux arrays in
four immediately consecutive `mp_assemble` calls. No caller consumes an
individual direction before all four calls finish. Packing the four arrays in
a fixed order, applying one element-wise sum reduction, and unpacking them
therefore preserves the synchronization point and every result while reducing
these collective calls by four times.

The arrays contain one owning rank's value and zeros for every other rank, so
the packed reduction cannot change a floating-point addition sequence among
multiple nonzero contributors. A thread-private reusable work buffer avoids
adding allocation overhead to the fast barotropic path.

Expected 4n64-16ppn DEMO evidence:

- region 49 aggregate calls decrease materially on the affected grids;
- region 49 and total PROFILE wall decrease without moving time into another
  MPI region;
- region 53/55 computation and all non-target numerical work remain
  unchanged apart from reduced wait time;
- `run_report.json` has `passed=true`, `normal_end=true`,
  `outputs.passed=true`, and `comparison.passed=true`;
- all 26 file/variable comparisons remain bitwise identical.

No model equation, physical input, time step, interpolation, mask, compiler
setting, or profiling instrumentation is changed.

## Result

- Clean build: job `118628741`, PASS; candidate
  `Local_Lab/runs/validation/candidate_20260805T120518Z_2096`; binary SHA-256
  `1b1ee471fcd70915ab1e68899a0734dfa1e7cd8547780604b6d12259bb09981b`.
- 4n64-16ppn DEMO: job `118628926`, PASS; run
  `Local_Lab/runs/profile128/batch-boundary-flux-4n64-16ppn_20260805T121107Z_58978`.
- Correctness: normal end; all 26 comparisons have `RMSE=0` and
  `max_abs=0`.
- PROFILE total (mean of the two grid totals): `117.744595 s` to
  `116.699195 s` (`-0.89%`). Slurm elapsed wall: `121.87 s` to `118.99 s`.
- Grid 1 region 49 calls per rank: `799678` to `201178` (`-74.84%`);
  wall mean: `29.923821 s` to `26.622368 s` (`-11.03%`).
- Grid 2 region 49 calls per rank: `144876` to `38202` (`-73.63%`);
  wall mean moved from `15.671707 s` to `18.576998 s`. Other inclusive
  region timings also moved in both directions, while overall wall improved.

Accepted under the project's logic-first rule: the intended collective-count
reduction is directly observed, correctness is bitwise identical, and total
runtime has no regression. The single-run region-wall redistribution is not
treated as proof of a Grid 2 speedup.
