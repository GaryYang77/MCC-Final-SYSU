# Skip tile-local all-land rows in biology

- Accepted anchor: `6e9e0920b19642de301077f9fc0bbd9850ea0bc4e`.
- Reference: `Local_Lab/runs/profile128/tracer-vdiff-direct-rhs-4n64-16ppn_20260807T151528Z_54133`
  (job `118741183`, 4n64/16ppn, `8x8`, 60/300; resource wall
  `78.40 s`; all 26 comparisons bitwise zero).
- Target: biology source/sink region 15, without changing the vectorized
  `k -> i` loops used for rows containing ocean cells.
- Evidence: `SCS_grd.nc` has a wet fraction of 65.32%; under an 8x8 split,
  575/2624 (21.9%) tile-local row slices are entirely dry. The Dongsha60 grid
  is 100% wet, so this experiment can only reduce Grid 1 biology work. Biology
  computations are column-local and masked land cells do not contribute to
  wet-cell tracer fluxes.
- Hypothesis: cycle the outer `J_LOOP` when the current tile's complete
  `rmask(Istr:Iend,j)` slice is zero. Wet rows retain their exact loop order and
  arithmetic, while all work for provably inactive land-only rows is avoided.
- Scope: `ROMS_CoSiNE15/ROMS/Nonlinear/Biology/bio_UMAINE15.h`, one
  `MASKING`-guarded row test. No profiling, input, precision, MPI, or wet-cell
  formula changes.
- Expected numerical behavior: wet output cells remain bitwise identical;
  masked land state may avoid otherwise unused biology updates. Lower Grid 1
  R15, unchanged Grid 2 R15, and lower or neutral total wall.
- Falsifier: abnormal end, any nonzero DEMO comparison error, wet-cell change,
  or row-scan overhead outweighing the saved Grid 1 work.
- Validation: this changes mask-path control flow, so a passing DEMO must be
  followed by the triggered one-rank validation before commit.

## Result

- Clean PROFILE build: job `118741295`, candidate
  `Local_Lab/runs/validation/candidate_20260807T152507Z_3876`, binary SHA-256
  `a7c0fd61ce1d85b0d69ee478c267e3b6d27502e1bf992ce30ff6551492a752dd`.
- Three identical 4n64 DEMO submissions were produced after intermittent SSH
  output hid the first two completed `sbatch --wait` launches. All three ended
  normally, passed the output contract, and kept all 26 comparison metrics at
  `RMSE=0` and `max_abs=0`:
  - job `118741769`: resource wall `79.58 s`, Grid 1 R15 `1.063026 s`;
  - job `118741954`: resource wall `79.97 s`, Grid 1 R15 `1.069923 s`;
  - job `118741982`: resource wall `77.51 s`, Grid 1 R15 `1.069017 s`.
- The accepted reference Grid 1 R15 was `1.259968 s`, so the target region
  improved by `15.1-15.6%` in all three allocations. Grid 2 R15 remained
  `3.434-3.437 s` versus `3.425 s`, as expected for its fully wet mask.
- End-to-end wall was dominated by unrelated Grid 1 R44 variation: R44 ranged
  from `3.423` to `5.876 s` versus `4.106 s` in the single reference. The
  candidate nevertheless delivered one faster total (`77.51 s` versus
  `78.40 s`) and a stable, causal reduction in the target region.
- Triggered one-rank validation: job `118742115`, candidate
  `candidate_20260807T154356Z_8794`, Slurm `COMPLETED` with exit code zero;
  `validation_report.json passed=true`, all comparisons within `1e-5`.
  Candidate model wall was `156.828 s` versus the sealed baseline
  `188.695 s` (compatibility evidence only, not a performance comparison).

Decision: accept. The change has a repeatable `~15%` target-region gain,
preserves all checked wet outputs bitwise, passes the independent validation,
and has no demonstrated causal regression outside noisy R44 timing.
