# Phase 4 optimization summary

## Frozen result

- Source: commit `e7e0ce1` (`perf(biology): hoist shallow-water light factor`).
- Daily configuration: 4 nodes, 64 ranks, 16 ranks/node, `8x8`, 60/300
  steps.
- Final same-allocation pair: job `118814005`, PROFILE `69.96 s`, no-profile
  `71.87 s`; both runs ended normally and all 26 variables were bitwise
  identical.
- The best observed no-profile DEMO remains `71.72 s` at `0458b06`.  The
  `0.15 s` difference from the final source is below short-run allocation and
  order noise.  The final source is retained because its later changes each
  reduced their intended region without a causal guard regression.
- PROFILE and no-profile are deliberately reported separately.  The phase did
  not prove a no-profile result below 70 seconds.

Evidence:

- `profile_bundle_logs/phase-current-paired-on_20260809T052757Z_profile_bundle.json`
- `profile_bundle_logs/phase-current-paired_20260809T052757Z_overhead_report.json`
- `profile_bundle_logs/all-wet-mask-phase-paired-overhead-on_20260809T022450Z_profile_bundle.json`

## Accepted work

The profiler-v2 evidence shifted the work from coarse whole-routine guesses to
small transformations inside the measured kernels.  The accepted commits since
the profiler-v2 workflow was fixed are:

- `1cb989f`, `be06007`: reuse corrector and predictor tracer transport planes,
  reducing repeated allocation and plane reconstruction.
- `89e8af1`: place selected `step2d`/predictor work arrays on the stack; R09 fell
  about 3% and R22 about 12% in the acceptance run.
- `89d0a70`, `ed04ce3`: cache invariant horizontal and time metrics in tracer
  corrector/predictor loops.
- `d2d4fc6`, `07f8d83`, `7a7f561`: specialize K-kl unit powers and boundary
  powers.  The first two main R19 steps each reduced both grids by about 11%;
  the boundary specialization added roughly 3-5% within R19.
- `d68e187`: cache corrector C4 transport half planes; R35 fell 1.4-1.5%.
- `c28c20c`, `c76d25c`: cache and combine biharmonic tracer-mixing face
  coefficients; R27 fell 15-20%, then another 6-11%.
- `5904040`: overlap 4-D halo sends with local unpacking; R42 fell 4-6%.
- `2c3d9b6`: batch predictor surface halo exchanges; R40 calls fell 8.39%.
- `077545b`, `0458b06`: detect all-wet tiles/faces and skip multiplication by
  unit masks in the tracer corrector.  The cumulative no-profile score improved
  from `73.10 s` at `c76d25c` to the best observed `71.72 s` at `0458b06`.
- `182673a`: extend the all-wet mask fast path to the predictor; Grid-2 R22 fell
  1.64% and the score run reached `70.18 s`.
- `6e085fc`, `94e1bab`: cache predictor C4 half transports and reuse passive
  tracer vertical-diffusion coefficients; Grid-2 R22 fell another 1.31% and
  2.06%, respectively.
- `e7e0ce1`: hoist the shallow-water biology light exponent outside the depth
  loop; small but matching R15 reductions on both grids.

Every accepted model change completed the required 4n64 gate with exact output.
Changes involving masks, MPI synchronization, or arithmetic specialization also
ran the triggered independent validation where required; individual job IDs and
binary hashes are in `Local_Lab/experiments/`.

## Important rejected experiments

- Fusing C4 difference and gradient loops regressed R35 by about 10-13%, likely
  by losing vectorization.  Keep the vector-friendly plane loops.
- Batching two `put_refine2d` momentum halo calls through a 3-D exchange doubled
  the normalized R40/R41 share (`6.84% -> 13.70%`).  Dimensional batching is not
  automatically cheaper.
- A `put_refine3d` endpoint fast path reduced R54 only about 0.9%, below its
  acceptance threshold.
- Giving `get_contact2d` a route-plan key preserved bitwise results but selected
  the existing sparse-peer transport: R49 rose by 112-142%, Grid-2 nesting by
  84%, and total by 42%.  If plan caching is revisited, cache the plan while
  retaining dense `MPI_Alltoallv`; do not reuse this keyed sparse path.
- Broad algebraic rewrites, reciprocal substitutions, blanket IVDEP directives,
  generic buffer reuse, and more aggressive nonblocking exchange variants were
  either neutral, noisy, or regressive.  Compiler friendliness must be measured,
  not inferred from fewer source operations.

## Lessons and next directions

1. A PROFILE total is a screening signal, not the competition score.  R03/R44
   and MPI scheduling can move the short-run total by seconds; accept small work
   only with a matching target-region mechanism, then periodically pair against
   no-profile in one allocation.
2. Fully wet Grid 2 makes mask specialization useful, while mixed Grid 1 needs a
   guarded fallback.  Similar static-domain guards remain worth looking for.
3. Remaining large kernels are R35 tracer corrector, R22 predictor, R19 GLS,
   R09 2-D kernel, and high-frequency halo/point communication.  Most easy
   redundancy has already been removed, so future gains will probably be
   several 0.1-0.5 second improvements rather than one large patch.
4. Before touching R49 again, extend diagnostic coverage to the currently
   unclassified assemble modes.  Separate plan construction, packing, MPI wait,
   and unpacking, and record payload distributions.  A transport should be
   selected by measured message topology rather than by “sparse” versus “dense”
   labels.
5. For R22/R35/R09, use ifort vectorization reports on the exact hot loops.
   Preserve the inner contiguous loop and floating-point order; test one loop
   transformation at a time.
6. The next authoritative result should be a full three-day, same-source
   no-profile run followed by official `vali.py`.  The requested 4n96 tests are
   useful scaling evidence, but the competition submission configuration must
   still be selected from aligned full-run measurements.
