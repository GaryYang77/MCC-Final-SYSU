# MCC 2026 ROMS-CoSiNE15 Phase 3 Handoff

## Mission

Continue phase 3 without changing the physical scheme, inputs, numerical
contract, or profiling instrumentation. The fixed KPI remains the 4-node,
64-rank, 16 ranks/node, `8x8`, 60/300-step PROFILE DEMO: reduce the phase-2
`80.282807 s` result by 30%, to `<=56.197965 s`, under the workflow in
`AGENTS.md`.

The KPI is **not achieved**. Current accepted main measures `78.148727 s`;
the best observed phase-3 run was `78.041478 s` at commit `eb8ba58`. Treat the
goal as active rather than complete.

## Authoritative repository state

- Branch: `main` only; all local experiment branches were merged and deleted.
- HEAD after evidence archival: `ecfc424` (`perf(data): record phase 3 full
  scaling results`).
- The worktree was clean after the final audit and the local test suite had
  `43 passed`.
- Local `main` is eight commits ahead of `origin/main`; no push was performed.
  Coordinate and run `git push origin main` before another engineer relies on
  the remote branch.
- Read `AGENTS.md` in full before acting. It defines cluster access, immutable
  profiling, single-hypothesis branches, build/DEMO/validate gates, failure
  recovery, and final official validation.
- Main analysis: `Local_Lab/profiling-analysis.md`.
- Accepted experiment evidence: `Local_Lab/experiments/`.
- Do not rerun the sealed baseline.

## Accepted phase-3 source commits

Use `git show` and the corresponding experiment Markdown rather than this
handoff for implementation details.

- `0db324f`: reuse tracer vertical-diffusion factorization.
- `11f077b`: reuse identical GLS dissipation powers.
- `c81602a`: reuse identical GLS wall-function powers.
- `76f549f`: cache `get_contact3d` route plans.
- `eb8ba58`: reuse `fine2coarse3d` workspaces.
- `ddf22ce`: cache fine-to-coarse sum route plans.
- `9b804ef`: cache crossing-cell route plans.
- `ecfc424`: data-only commit archiving the latest complete runs.

All accepted source candidates passed the 4n64 DEMO comparison with all 26
metrics at `RMSE=0, max_abs=0`. Triggered one-rank validations are documented
in the experiment files. Profiling source was never changed.

## Latest complete three-day evidence

The canonical suite record is
`profile_bundle_logs/phase3-full-suite_20260806T105925Z_53017_summary.txt`;
binary hashes are in the adjacent `_binaries.txt` file. The three bundles and
official validation transcripts are in `profile_bundle_logs/` with matching
configuration/run timestamps.

- PROFILE 4n64, `8x8`, job `118678678`: model wall `2993.91 s`, profile totals
  `2991.941/2991.943 s`; 26 comparisons bitwise zero; official `vali.py` PASS.
- no-profile 4n64, `8x8`, job `118679841`: model wall `2973.35 s`, Slurm
  elapsed `2975 s`; 26 comparisons bitwise zero; official `vali.py` PASS.
- no-profile 4n96, 24 ranks/node, `8x12`, job `118681002`: model wall
  `2729.97 s`, Slurm elapsed `2732 s`; 26 comparisons bitwise zero; official
  `vali.py` PASS.
- The 4n96 60/300 no-profile preflight was `74.21 s`, also bitwise zero.

The 4n96 full run is `8.19%` faster than the same no-profile 4n64 binary. This
makes 96 ranks a strong final-allocation candidate, but it does not silently
replace the explicitly fixed 4n64 phase-3 KPI. Keep KPI measurements on 4n64
unless the team formally changes the target, and carry 96 ranks as a separate
final runtime configuration.

The requested no-profile 4n128/32ppn/`8x16` full run had **not started** at
handoff time: no Slurm job and no staged run directory existed. Run it with
the same no-profile binary recorded in `_binaries.txt`, using the successful
4n64 no-profile full run as `--reference-run`. Use `--no-expect-profile`,
`--preserve-output-cadence`, and official `vali.py` afterward.

## Failed evidence that must not be rediscovered blindly

Detailed records are retained on this workstation under `/tmp/*-failed/`.
Important results:

- Cross-rank fine-to-coarse partial sums were fast (`-22.44%`) but changed
  floating-point order and produced `1e-3`-scale errors.
- Sending every raw donor block restored exactness but regressed to about
  `469.53 s`; the accepted hybrid representation is the viable compromise.
- `MPI_Reduce + MPI_Bcast` was much slower than HPC-X `MPI_Allreduce`.
- Batching all tracer contact records increased region 53 by 28% and RSS by
  9.7% because of a noncontiguous temporary.
- Broad GLS K-kl power specialization cut region 19 by about 56% and reached
  `76.683069 s`, but 25/26 variables failed the tolerance gate. Only
  bitwise-safe common-subexpression reuse survived.
- Predictor coefficient reuse improved region 22 by about 1.9% twice but
  regressed total wall twice.
- Persistent cached route buffers regressed total by 2.57% and region 49;
  do not assume allocator removal is automatically beneficial.
- Global `-no-heap-arrays` regressed total by 2.54% and GLS by 10.42%.
- Object-local `-no-heap-arrays` improved regions 9/22 by only 0.74/1.13%
  while total regressed 1.28%; it was the final rejected experiment.
- Contact-major receiver traversal had no measurable benefit.

Inherited negative evidence also includes unsupported AVX selection, generic
extra compiler flags, MPI environment tuning, 4x16/16x4 tile trials,
`NO_CORRECT_TRACER`, and several failed Batch-Fsum rewrites. Revisit only with
a materially new falsifiable hypothesis.

## Recommended next technical direction

The easy global replication wins are already harvested. Route-plan caches now
produce sub-percent effects and cannot bridge the remaining ~22 seconds.

1. **Direct pack for contact routing.** Eliminate the remaining
   `Ad -> Ac -> Asend -> Arecv -> Ac` copies. Use the accepted static route
   plan to write donor values directly into a compact send buffer and receive
   directly into the receiver-local contact representation. Preserve contact,
   vertical-level, donor-point, and unpack order exactly.
2. **Direct pack for fine-to-coarse.** Compute ordered complete-block sums and
   crossing records into the compact routed layout, removing
   `Fsum/Fcross -> Asend` scans. Never alter the within-block accumulation
   order that previously caused validation failure.
3. **Only then test sparse peers.** Replace global `MPI_Alltoallv` with cached
   active-peer `Irecv/Isend/Waitall` after direct pack is correct. Changing a
   collective alone has poor prior evidence on this HPC-X version.
4. **Compute kernels via compiler reports.** Use ifort vector/loop reports on
   `step3d_t.F`, `pre_step3d.F`, `step2d.F`, and `gls_corstep.F`; do not edit
   profiling. Make one local, order-preserving loop/data-access change per
   experiment. Remaining 4n64 Grid-2 signals include R35 ~9.32 s, R22 ~8.27
   s, R19 ~6.42 s, R9 ~5.67 s, and nesting R39 ~9.99 s.
5. Before a final submission, individually ablate logic-only commits whose
   total benefit was not stable (`b6c435b`, `f8bee18`, `6b52c29`, and the two
   smallest route-plan caches). One revert per hypothesis; do not bundle them.

## Safe restart checklist

1. Confirm `git status --short` is empty and HEAD is `ecfc424` or a known
   descendant; ensure the eight local commits are pushed/available.
2. Read `AGENTS.md`, the latest full-suite summary, and the specific accepted
   experiment files before selecting a hotspot.
3. Create `perf/<single-hypothesis>` from clean main and record the full anchor
   SHA in a new experiment Markdown.
4. Keep the current 4n64 accepted DEMO reference:
   `Local_Lab/runs/profile128/cache-crossing-route-plan-4n64-16ppn_20260806T072734Z_65169`.
5. Run local tests, a clean PROFILE build, and one 4n64 60/300 DEMO as defined
   in `AGENTS.md`; trigger one-rank validation only under its listed rules.
6. Do not run another full three-day case until a cumulative candidate is
   selected. For final timing, compare no-profile 64/96/128 allocations and
   run official `vali.py` on the chosen case.

## Suggested skills

- `diagnose`: use its evidence-first loop for MPI/performance regressions;
  run `setup-matt-pocock-skills` first if the next environment requires it.
- `zoom-out`: use before changing unfamiliar nesting or distribution code to
  map ownership, data flow, and invariants.
- `handoff`: regenerate a compact successor document when the next engineer
  stops, referencing experiment artifacts instead of duplicating them.

