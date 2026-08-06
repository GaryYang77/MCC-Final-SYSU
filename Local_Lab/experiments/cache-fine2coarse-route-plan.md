# Cache fine2coarse3d sum route plans

- Accepted anchor: `eb8ba58b231d98cff02dd39740ccc4dcb77747b0`.
- Reference: `reuse-fine2coarse-workspace-4n64-16ppn_20260806T063348Z_17558`.
- Targets: Grid 2 region 55 (`5.837665 s`), region 39 (`9.914756 s`), and
  region 49 (`3.353911 s`).
- Evidence: the accepted `Fsum` Owner+Receiver call uses the same static
  `F2Cowner/Rowner` route for every variable, but it does not provide a plan
  key and therefore rebuilds counts, displacements, and record traversal on
  every call.
- Hypothesis: identify the F2C route by contact region and absolute C-grid
  type, using a negative key namespace distinct from `get_contact3d`. This
  activates the accepted route-plan cache without changing pack order,
  `MPI_Alltoallv`, unpack order, or payload.
- No physical arithmetic, floating-point order, input, or profiling code
  changes.
- Expected numerical behavior: bitwise-identical output and lower region
  49/55/39 and total wall.
- Falsifier: any MPI/correctness failure, plan collision, changed call count,
  or no useful target/total improvement.

## Result: accepted

- The first build job `118665653` failed before linking because `Fsum` is a
  rank-2 array and therefore resolves to `mp_assemblef_2d`, while the initial
  draft only exposed `PlanKey` on the rank-3 specific. The corrected draft
  added the same keyed Owner+Receiver plan path to the 2D specific and kept
  every no-key call on its original implementation.
- Corrected build job `118666034`; candidate
  `candidate_20260806T065148Z_6320`; binary SHA-256
  `9c330272a1fcdbaae04601a08b89e87d5c4e9930285a29e5377680af5e4c2101`.
- DEMO job `118666504`, run
  `cache-fine2coarse-route-plan-4n64-16ppn_20260806T065835Z_35945`:
  normal end, complete outputs, and all 26 variables had `RMSE=0,
  max_abs=0`.
- Grid 1 region 49: `4.850147 -> 4.684067 s` (`-3.43%`); Grid 2 region
  49: `3.353911 -> 3.330505 s` (`-0.70%`). Grid 2 region 39 changed from
  `9.914756 s` to `9.903396 s` (`-0.11%`); region 55 changed from
  `5.837665 s` to `5.856541 s` (`+0.32%`). Total changed from
  `78.041478 s` to `78.541761 s` (`+0.64%`), dominated by an unrelated
  `+0.848 s` Grid 1 region-44 variation. The targeted MPI region improved
  without a material total-path regression, satisfying the team's relaxed
  acceptance rule.
- Triggered 1-rank validation job `118666719`, candidate
  `candidate_20260806T070300Z_3313`: `passed=true`. Its `198.675 s` timing is
  not performance evidence because the 64-rank-only cache is inactive and
  this gate is used only for fallback/generic compatibility.
