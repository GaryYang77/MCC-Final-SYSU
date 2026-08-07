# Sparse active-peer routing for fine-to-coarse assembly plans (rerun)

- Accepted anchor: `c0b7e2a32183114221181f976e32cb9a2529192b`.
- Reference: `sparse-peer-contact3d-4n64-16ppn_20260806T181956Z_31080`
  (total `76.450 s`).
- Background: the first attempt (2026-08-07, archived under
  `/tmp/sparse-peer-f2c-failed/`) replaced the dense `MPI_Alltoallv` with a
  shared `Irecv -> Isend -> Waitall` active-peer exchange in the keyed 2D
  F2C sum plan and the 3D crossing plan.  The DEMO was bitwise identical
  and Grid 2 region 49 improved `3.346 -> 3.016 s`, but the single-run
  total regressed `76.450 -> 78.528 s` because the unrelated Grid 1 R44
  output-I/O broadcast region varied from `3.352` to `5.241 s`.
- Team decision (2026-08-07): rerun the candidate against the same
  reference to separate the targeted gain from R44 noise.
- Hypothesis unchanged: the F2C keyed plans exchange with only a few
  active peers; replacing the dense collective with a cached
  sparse active-peer exchange preserves buffers, offsets, message order,
  and payload, so results stay bitwise identical while region 49/55 and
  total wall improve.
- Scope: `distribute.F` only (one shared `mp_sparse_exchange` helper used
  by `mp_assemble_contact3d` and the two generic keyed plan paths).  No
  profiling source changes.
- Expected numerical behavior: bitwise-identical output and lower region
  49/55 and total wall.
- Falsifier: MPI hang/error, tag mismatch, changed call count, nonzero
  DEMO comparison error, or no useful target/total improvement.

## Result: accepted (team-approved reruns)

- Build job `118715012`; candidate
  `candidate_20260807T040818Z_20842`; binary SHA-256
  `eb1e08bbecd61fc31e3daddbf1e225166c1a2acc37084de0dc3f1c091f9d3a58`
  (byte-identical to the original sparse-peer-f2c candidate build).
- Rerun 1 (job `118715178`, run
  `sparse-peer-f2c-rerun-4n64-16ppn_20260807T041435Z_57059`): PASS,
  bitwise identical.  Grid 2 R49 `3.346 -> 3.070 s`, R55
  `5.874 -> 5.429 s`, R39 `9.916 -> 9.498 s`; total `84.10 s` because the
  unrelated Grid 1 R44 output-I/O region spiked to `9.105 s`.
- Rerun 2 (job `118715385`, run
  `sparse-peer-f2c-rerun2-4n64-16ppn_20260807T041804Z_20245`): PASS,
  bitwise identical.  Grid 2 R49 `3.346 -> 3.009 s`, R55
  `5.874 -> 5.418 s`, R39 `9.916 -> 9.539 s`; total `79.51 s` with Grid 1
  R44 at `5.739 s`.
- The targeted gain reproduced on all three runs of this binary (original
  2026-08-07 attempt plus both reruns): Grid 2 R49 -8.2% to -10.1%, R55
  -7.6% to -7.8%, R39 -3.8% to -4.2%, always with `RMSE=0/max_abs=0`.
  The single-run total comparisons remain dominated by the R44
  output-I/O region, which varies `3.35-9.11 s` across otherwise
  identical-code runs (see `note-r44-output-io.md`).  Team decision:
  accept on the reproduced targeted-region evidence and bitwise identity.
- Triggered 1-rank validation job `118715514`, candidate
  `candidate_20260807T042140Z_12474`: `passed=true`; candidate wall was
  `161.360 s` versus sealed baseline `188.695 s`.  Compatibility evidence;
  the DEMO comparison is the distributed correctness gate.
