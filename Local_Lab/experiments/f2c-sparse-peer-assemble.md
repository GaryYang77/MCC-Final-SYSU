# Sparse active-peer routing for mp_assemble_f2csum

- Accepted anchor: `5474149fe9d8ad343235c1c9f6e04df6d1db3de1`.
- Reference: latest accepted 4n64-16ppn DEMO run (recorded at run time below).
- Background: `mp_assemble_f2csum` (region 49, direct-pack fine-to-coarse
  block-sum assembly, commit `1760c60`) already accumulates complete donor
  blocks straight into the send buffer, but still exchanges with the dense
  `MPI_Alltoallv`. The shared `mp_sparse_exchange` helper (cached
  `Irecv -> Isend -> Waitall` over only active peers) is already used by
  `mp_assemble_contact3d` and the generic `mp_assemblef_2d`/`mp_assemblef_3d`
  keyed plans, and was independently validated bitwise-identical for F2C-style
  traffic in `sparse-peer-f2c-rerun.md`. This experiment closes the one
  remaining gap: wiring `mp_sparse_exchange` into `mp_assemble_f2csum` itself.
- Hypothesis: replacing `mpi_alltoallv` with `mp_sparse_exchange` in
  `mp_assemble_f2csum` preserves the exact per-peer counts/displacements and
  packed buffer contents (only the transport primitive changes), so the DEMO
  stays bitwise identical while region 49 (and possibly 39/55) wall time
  drops because most peers have zero F2C traffic.
- Scope: `ROMS_CoSiNE15/ROMS/Utility/distribute.F`, `mp_assemble_f2csum` only
  (single call-site swap of `mpi_alltoallv` for `mp_sparse_exchange`). No
  profiling source changes, no call-site or gating changes elsewhere.
- Expected numerical behavior: bitwise-identical output; lower or unchanged
  region 49 wall; no other region should be affected.
- Falsifier: build failure, nonzero DEMO comparison error, changed call
  count, MPI hang/error, or no measurable target-region improvement.

## Result: accepted

- The sealed reference chain's `output/` directories had already been
  purged by cluster housekeeping, so a fresh same-session mainline
  baseline (`session-mainline-baseline-4n64-16ppn_20260807T102418Z`) was
  built and run against this candidate's own DEMO output to obtain a
  valid comparison. Both directions passed with all 26 metrics
  `RMSE=0, max_abs=0`.
- Two paired DEMO runs against that mainline baseline reproduced the
  targeted-region gain: Grid 1 R49 `3.575 -> 3.374/3.360 s` (-5.6%/-6.0%),
  Grid 2 R49 `3.313 -> 3.153/3.077 s` (-4.8%/-7.1%), Grid 2 R55
  `5.443 -> 5.213/5.180 s` (-4.2%/-4.9%), Grid 2 R39
  `9.488 -> 9.251/9.233 s` (-2.5%/-2.7%). Total wall varied with the
  known R44 forcing-broadcast noise (+1.8s then -2.85s), consistent with
  `note-r44-output-io.md`.
- Triggered 1-rank validate (job `118738661`, candidate
  `candidate_20260807T134310Z_9635`): PASS, `RMSE`/`max_abs` <= 1e-5;
  1-rank timing `171.177 s` vs sealed baseline `188.695 s` (+9.28%,
  compatibility evidence only).
- Accepted on reproduced targeted-region evidence and confirmed bitwise
  identity, following the same protocol as `f2c-direct-pack-rerun.md` and
  `sparse-peer-f2c-rerun.md`.
