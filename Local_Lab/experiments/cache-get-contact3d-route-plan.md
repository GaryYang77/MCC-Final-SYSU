# Cache get_contact3d route plans

- Accepted anchor: `c81602a92346ba8566dc932df50dde5a47217060`.
- Reference: `reuse-gls-wall-powers-4n64-16ppn_20260806T043445Z_52399`.
- Targets: Grid 1/2 region 49 (`4.964241/3.440183 s`) and Grid 1 region 53
  (`get_contact3d` donor extraction and routing).
- Evidence: the accepted donor-to-receiver path in `mp_assemblef_3d` rebuilds
  send/receive counts, displacements, offsets, and record traversal on every
  call. `contact(cr)%Downer` and `%Rowner`, grid decomposition, contact order,
  and array shape are static throughout the time loop.
- Hypothesis: let `get_contact3d` explicitly identify its stable contact map
  with a key combining `cr` and the R/U/V C-grid type. Cache the resulting
  counts/displacements plus ordered
  send, receive, and zero-record indices per grid/model/key/rank-count/shape.
  Subsequent calls retain the same element-wise pack order, unchanged
  `MPI_Alltoallv`, and the same element-wise unpack order without rescanning
  every global contact or rebuilding the communication plan.
- Scope is deliberately limited to the high-frequency 3D Owner+Receiver path.
  Calls without an explicit plan key, owner-only collectives, 2D routes, and
  crossing-cell routes retain their accepted implementation.
- No physical arithmetic, floating-point reduction, MPI payload, peer count,
  or profiling code changes.
- Expected numerical behavior: bitwise-identical output and lower region
  49/53 and total wall.
- Falsifier: any MPI/correctness failure, plan collision, changed call count,
  or no useful target/total improvement.

## Result: accepted

- Build job `118663292`; candidate
  `candidate_20260806T055935Z_3704`; binary SHA-256
  `68629cd74ce1ca1f6b045c5097c4c73ee4d27120d08981c74840163dbe6c5158`.
- DEMO job `118663526`, run
  `cache-get-contact3d-route-plan-4n64-16ppn_20260806T060558Z_28995`:
  normal end, complete outputs, and all 26 variables had `RMSE=0,
  max_abs=0`.
- Grid 1 region 49: `4.964241 -> 4.844495 s` (`-2.41%`). Grid 2
  region 49: `3.440183 -> 3.429593 s` (`-0.31%`). Total improved from
  `81.892702 s` to `79.501144 s` (`-2.92%`). Region 44 also varied, so the
  total delta is not attributed entirely to this change; the targeted region
  nevertheless improved without a visible non-target regression.
- Triggered 1-rank validation job `118663749`, candidate
  `candidate_20260806T061043Z_10793`: `passed=true`; candidate wall was
  `157.327 s` versus sealed baseline `188.695 s`. The 1-rank path does not
  activate this 64-rank route cache and is supporting compatibility evidence;
  the DEMO comparison is the distributed correctness gate.
