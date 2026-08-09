# Skip unit U/V masks in all-wet tracer-advection tiles

- Accepted anchor: `077545bd85dd032e9e976613af0ff870ec1fb437`
  (`perf(tracer): skip final mask on all-wet tiles`).
- Reference run:
  `Local_Lab/runs/profile128/tracer-all-wet-final-mask-4n64-16ppn_20260809T012419Z_39605`
  (job `118808175`, 4n64/16ppn, 8x8, 60/300; profile total `72.58 s`,
  all 26 comparisons bitwise zero).
- Target: Grid-1/2 R35, specifically profiler-v2 horizontal tracer
  advection site 132.
- Guard regions: R09, R19, R22, R39, R44, R49, R54 and R55.

## Falsifiable hypothesis

The active C4 horizontal tracer-advection stencil first constructs tracer
differences and then multiplies every U/V face by the static `umask` or
`vmask`.  The same masks are revisited for every one of 34 levels and 15
tracers.  Grid 2 is fully wet, so those loads and multiplications are
redundant there.

Scan the exact U- and V-mask ranges once per tile call.  An all-unit range
uses a loop that stores the same tracer difference without the subsequent
multiply by one; any range containing a non-unit mask uses the original loop
unchanged.  The mask decision is outside the level/tracer loops.  Curvature,
flux and update expressions, loop bounds, model equations, precision, MPI,
inputs and profiler sources are unchanged.  MPDATA and non-MASKING builds
retain their prior paths.

Expected output is bitwise identical.  Expected performance evidence is a
lower Grid-2 R35 with unchanged calls and stable guards; Grid-1 may pay a
small one-time scan on mixed tiles.  A build failure, any nonzero comparison,
or no useful Grid-2 target direction rejects the experiment.  This changes
mask control flow, so an accepted DEMO must also pass independent 1-rank
validation before commit.

## Result

Accepted as a small cumulative improvement.

- Clean score build: job `118808413`, candidate
  `Local_Lab/runs/validation/candidate_20260809T014341Z_965`; binary SHA-256
  `6c04dd33b8d77e7af25c8f65de752b4caf739521e4bd2743968b8c789f5ce4ba`.
- 4n64 score DEMO: job `118808466`, run
  `Local_Lab/runs/profile128/tracer-all-wet-horizontal-mask-4n64-16ppn_20260809T015113Z_31317`.
  It ended normally, all output/profile checks passed, and all 26 variables
  had `RMSE=0` and `max_abs=0`.
- R35 moved in the intended direction on both grids with unchanged calls:
  Grid 1 `3.2301 -> 3.2272 s` (`-0.09%`) and Grid 2
  `8.8480 -> 8.8133 s` (`-0.39%`, about `0.035 s`).  This is small but has no
  target-region regression and is consistent with eliminating only two mask
  loads/multiplies from a much larger stencil.
- Profile total changed `72.58 -> 70.98 s`, but that is not attributed to the
  candidate: volatile Grid-2 R44 fell `32.96%`, while R09 increased `1.88%`.
  The target R35 movement, not the noisy total, is the acceptance evidence.
- Because the broad R35 change was close to noise, profiler-v2 diagnostic
  summary job `118808606` was run from binary
  `17dc96e8261a53557054e5af1ab6571633c57d4868d60e0d7cac10dd01152c0c`:
  `Local_Lab/runs/profile128/tracer-all-wet-horizontal-mask-diagnostic-summary_20260809T020036Z_60414`.
  It passed all 64-rank/4-node metadata and parent-child consistency checks;
  sites 131--135 covered `99.95%/99.93%` of Grid-1/2 R35.  Grid-2 horizontal
  site 132 remained the dominant phase at `6.158 s` (`71.7%` of R35), and no
  work was displaced into another tracer phase.  The diagnostic absolute wall
  was not compared with score wall to claim a speedup.
- Independent 1-rank validation job `118808707`, candidate
  `Local_Lab/runs/validation/candidate_20260809T020419Z_3856`, passed all 13
  variables.  Its `142.474 s` time is compatibility evidence only.
- Evidence bundles:
  `profile_bundle_logs/tracer-all-wet-horizontal-mask-4n64-16ppn_20260809T015113Z_profile_bundle.json`
  and
  `profile_bundle_logs/tracer-all-wet-horizontal-mask-diagnostic-summary_20260809T020036Z_profile_bundle.json`.
