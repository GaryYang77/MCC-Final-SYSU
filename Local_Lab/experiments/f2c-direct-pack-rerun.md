# Direct pack for fine-to-coarse block sums (rerun)

- Accepted anchor: `8196341fae2085a5bb1c4c37e9e799f7734b8f04`.
- Reference: `sparse-peer-contact3d-4n64-16ppn_20260806T181956Z_31080`
  (total `76.450 s`).
- Background: the first attempt (2026-08-07, archived under
  `/tmp/f2c-direct-pack-failed/`) added `mp_assemble_f2csum`, which
  accumulates complete donor blocks directly into the MPI send buffer and
  unpacks receiver values into `Fine3dSum`, skipping the intermediate
  array write/read and its full zeroing.  The DEMO was bitwise identical
  and Grid 2 R39/R55 improved `9.916 -> 9.691 s` / `5.874 -> 5.595 s`, but
  the single-run total regressed `76.450 -> 76.803 s` because the
  unrelated Grid 1 R44 output-I/O region varied from `3.352` to `4.046 s`.
- Team decision (2026-08-07): rerun the candidate against the same
  reference.
- Hypothesis unchanged: the Fsum accumulation order
  (`Jadd` outer, `Iadd` inner, `k` outer) is preserved exactly, so the
  result stays bitwise identical while region 49/55 and total wall
  improve.
- Scope: `distribute.F` (`mp_assemble_f2csum`) and the `fine2coarse3d`
  call site, gated on `NtileI(dg)*NtileJ(dg) == numthreads` with the
  generic fallback retained.  No profiling source changes.
- Expected numerical behavior: bitwise-identical output and lower region
  49/55 and total wall.
- Falsifier: build failure, nonzero DEMO comparison error, changed call
  count, or no useful target/total improvement.

## Result: accepted (team-approved rerun)

- Build job `118715991`; candidate
  `candidate_20260807T043712Z_10671`; binary SHA-256
  `83b0ac39b37d73f27423b06aec8b54d90eae671c62ed542686f580a95df33e92`
  (byte-identical to the original f2c-direct-pack candidate build).
- Rerun DEMO (job `118716164`, run
  `f2c-direct-pack-rerun-4n64-16ppn_20260807T044323Z_31540`): PASS,
  bitwise identical.  Grid 2 R39 `9.916 -> 9.700 s`, R55
  `5.874 -> 5.615 s`; total `78.26 s` with the unrelated Grid 1 R44
  output-I/O region at `4.693 s` (reference run was the historical low
  `3.352 s`).
- The targeted gain reproduced on both runs of this binary (original
  2026-08-07 attempt and the rerun): R39 -0.2 s, R55 -0.26 to -0.31 s,
  always with `RMSE=0/max_abs=0`.  Total comparisons remain dominated by
  the R44 region (see `note-r44-output-io.md`).  Team decision: accept on
  the reproduced targeted-region evidence and bitwise identity.
- Triggered 1-rank validation job `118716250`, candidate
  `candidate_20260807T044708Z_26077`: `passed=true`; candidate wall was
  `168.249 s` versus sealed baseline `188.695 s`.  Compatibility evidence;
  the DEMO comparison is the distributed correctness gate.
