# Direct pack for get_contact3d contact routing

- Accepted anchor: `ecfc4242c967d045c1f2663d849caa5d44c00080`.
- Reference: `cache-crossing-route-plan-4n64-16ppn_20260806T072734Z_65169`.
- Targets: Grid 1 region 53 (`nesting_get_donor_data`) and region 49
  (`mpi_point_data_gathering`), plus the same keyed Owner+Receiver path in
  Grid 2 contact routing.
- Evidence: the accepted `get_contact3d` Owner+Receiver path extracts donor
  values into the contact array `Ac`, then the keyed `mp_assemblef_3d` plan
  copies those values from `Ac` into `Asend` on every call.  The donor
  indices, contact map, MPI decomposition, and array shapes are static, so
  the donor cell indices can be stored in the cached plan and the two passes
  fused into one `Ad -> Asend` pack.
- Hypothesis: write donor values directly into the compact send buffer using
  cached per-record `(i,j,ip1,jp1)` donor indices.  Keep record order,
  `MPI_Alltoallv` payload, receive order, zero records, and unpack order
  identical to the accepted implementation, and keep every no-key call and
  the Owner-only path unchanged.
- Expected numerical behavior: bitwise-identical output (no floating-point
  arithmetic is reordered or removed) and lower region 53/49 and total wall.
- Falsifier: any MPI/correctness failure, plan collision, changed call
  count, nonzero DEMO comparison error, or no useful target/total
  improvement.
- Scope: one new specialized `mp_assemble_contact3d` routine in
  `distribute.F` used only by `get_contact3d` when the grid tile count
  matches the rank count and receiver routing is active.  No profiling
  source changes.

## Result: accepted

- Build job `118690988`; candidate
  `candidate_20260806T174847Z_15017`; binary SHA-256
  `ad48bfdcb6a578c31229c6e2645b4c40184bb6dd3228d3b4ebd1290dc5cb9d36`.
- DEMO job `118691249`, run
  `direct-pack-contact3d-4n64-16ppn_20260806T175502Z_40915`: normal end,
  complete outputs, and all 26 variables had `RMSE=0, max_abs=0`.
- Grid 1 region 49: `4.846 -> 3.901 s` (`-19.5%`); Grid 1 region 53
  `nesting_get_donor_data`: `1.879 -> 0.934 s` (`-50.3%`). Grid 2 region 49
  `3.311 -> 3.340 s` (`+0.9%`, unchanged path and within run noise); Grid 2
  region 39 `9.988 -> 9.883 s` (`-1.1%`). Total changed from
  `78.149 s` to `77.734 s` (`-0.53%`). Region 49 call counts are unchanged
  on both grids, and no non-target region regressed materially.
- Debug history: two earlier candidate builds blew up because the donor
  array `Ad` is a per-tile local section in distributed ROMS while
  `get_contact3d` declares `Ad(LBi:,LBj:,LBk:)` with tile-offset lower
  bounds.  Passing that assumed-shape actual into another assumed-shape
  dummy under ifort 2017 yields bounds `1:SIZE` instead of the declared
  tile offsets, so packing with global donor indices read out of bounds.
  The accepted implementation stores tile-local donor positions
  (`Idg-LBi+1`, `Jdg-LBj+1`, clamped `ip1/jp1`) in the cached plan and
  indexes `Ad` from `LBOUND(Ad,...)` so the mapping matches the extraction
  loop bit-for-bit.  A temporary in-routine bitwise comparison of the
  direct pack against the accepted `Ac -> Asend` pack found zero
  mismatches inside the packed region.
- The donor-side extraction into `Ac` is skipped only for the keyed
  Owner+Receiver path (`UseLocalList` and `UseReceiver`); every consumer of
  `Ac` on receiver ranks is still populated by the receive unpack, and all
  no-key / Owner-only / non-matching-tile calls keep the accepted
  implementation.
- Triggered 1-rank validation job `118691411`, candidate
  `candidate_20260806T175831Z_15766`: `passed=true`; candidate wall was
  `159.920 s` versus sealed baseline `188.695 s`. The 1-rank path does not
  activate the 64-rank direct-pack plan and is supporting compatibility
  evidence; the DEMO comparison is the distributed correctness gate.
