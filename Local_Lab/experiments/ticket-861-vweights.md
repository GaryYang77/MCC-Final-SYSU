# Ticket #861 vertical-weights experiment

- Accepted commit / rollback anchor: `348dd3c88c8bf649576a722e01e56883d2e466ae`
- Branch: `perf/ticket-861-vweights`
- Upstream reference: ROMS commit `d85c993ccaa877ff9fc06db7911850f899a8601f` (`src:ticket:861`)
- Baseline binary SHA-256: `a9b08b31478da2546ca9ba7dc25ad2401afee78e63457e646a1428d84973a3e5`
- Accepted 2-node reference: `Local_Lab/runs/profile128/accepted-baseline-2n64_20260804T091640Z_5452`

## Falsifiable hypothesis

The supplied configuration is pure refinement: both grids have 34 vertical
levels and identical `Vtransform`, `Vstretching`, `THETA_S`, `THETA_B`, and
`TCLINE` values. Its contact metadata therefore does not require dynamic
vertical interpolation weights. Applying the upstream `get_Vweights` guard
should reduce nesting vertical-weights region 51 from about 5.1 seconds on
Grid 1 and 35.4 seconds on Grid 2 to near zero in the 4-node diagnostic. The
2-node, 64-rank, `8x8`, 60/300-step DEMO total wall time should fall materially,
with a working expectation of at least 15 percent.

This is elimination of redundant computation and associated MPI assembly, not
a change to the physical scheme. The 13 validation variables, dimensions,
masks, and finite-value checks must remain within the fixed `1e-5` gate; no
input file or profiling source may change.

## Results

- Local tests: `python -m pytest -q Local_Lab/tests`, 42 passed.
- Compiler/runtime: Intel 2017.5.239, HPC-X 2.7.4, NetCDF 4.4.1;
  `USE_MPI=on`, `USE_MPIF90=on`, `USE_NETCDF4=on`; compiler defaults
  `-heap-arrays -fp-model precise -ip -O3`.
- Cluster validation: job `118542209`, candidate
  `candidate_20260804T090525Z_21927`, binary SHA-256
  `4dad6d9476b31a50ab0d8d5f20744ac04d63963953e438e88107cb0119f8771f`.
  The wrapper exited zero, printed `[validate] PASS`, and the report has
  `passed=true`; the 4/20-step candidate took 176.863 seconds versus 188.695
  seconds for the sealed baseline.
- Reference DEMO: job `118542669`, 2 nodes, 64 ranks, `8x8`, outer/inner
  60/300 steps, wall 283.07 seconds, `passed=true`, `normal_end=true`.
- Candidate DEMO: job `118542853`, run
  `ticket-861-vweights-2n64_20260804T092249Z_53627`, same configuration,
  wall 239.95 seconds. This saves 43.12 seconds or 15.23 percent relative to
  the accepted 2-node reference (1.180x speedup).
- Correctness: `run_report.json` has `passed=true`, `normal_end=true`,
  `comparison.passed=true`, complete shapes for both output files, and all 26
  file/variable comparisons have `RMSE=0` and `max_abs=0`.
- Target region: Grid 1 region 51 fell from 4.3731724 seconds to 0.00007641
  seconds; Grid 2 fell from 31.027062 seconds to 0.000161275 seconds. Call
  counts remain 3968 and 19264 because profiling still measures the guarded
  section itself.
- Total-rank imbalance remains negligible: 1.000052 on Grid 1 and 1.000039
  on Grid 2. The leading remaining signals are Grid 1 region 49 point gather
  (46.75 seconds) and Grid 2 region 55/46 two-way coupling/data gather
  (60.35/58.97 seconds).

Conclusion: accept and commit. The hypothesis is confirmed, numerical output
is bitwise identical for all checked values, and the next experiment should
use this candidate run as its `--reference-run`.
