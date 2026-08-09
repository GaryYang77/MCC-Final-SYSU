# Batch predictor rzeta and zeta halo exchanges

Date: 2026-08-09

## Hypothesis

- Accepted parent: `590404077a09744edda6106c0d5850049fa64ad2`.
- Reference:
  `Local_Lab/runs/profile128/nonblocking-mp-exchange4d-4n64-16ppn_20260808T222611Z_22748`.
- Target: Grid 1/2 region 40 (`mpi_2d_halo_exchange`), currently about
  `0.791/2.604 s` mean with `1,954,880/9,566,464` aggregate calls.
- In each predictor fast step, `step2d_tile` exchanges `rzeta(:,:,krhs)` and
  then, after operations that do not read `rzeta`, exchanges
  `zeta(:,:,knew)`. Delay the first halo exchange and send both arrays in one
  existing `mp_exchange2d(Nvar=2)` call. Corrector steps keep the existing
  single-variable exchange.
- The same owned values, halos, peer ranks, direction order, and precision are
  retained. `rzeta` is fully synchronized before its next read. No arithmetic,
  equation, input, profiling code, or non-distributed result changes.
- Expected output is bitwise identical. Expected performance is at least 4%
  lower R40 mean on both grids, with lower R40 calls and neutral R09 compute.
  Any nonzero comparison, abnormal end, or absent causal R40 gain rejects the
  candidate.

## Result

- Clean PROFILE build job `118806643`; candidate
  `Local_Lab/runs/validation/candidate_20260808T235842Z_13202`; binary
  SHA-256 `201dbb458a14796d9cdaec80f60169e5d9eb13b585d76be4bdacbb5a5c88c7d5`.
- 4n64 DEMO job `118806901`; run
  `Local_Lab/runs/profile128/batch-step2d-zeta-halos-4n64-16ppn_20260809T000452Z_12870`.
- Normal end and all output/comparison gates passed; all 26 variables were
  bitwise identical.
- R40 aggregate calls fell by `8.39%` on both grids: Grid 1
  `1,954,880 -> 1,790,912`, Grid 2 `9,566,464 -> 8,760,064`.
- R40 mean fell `0.79081 -> 0.78304 s` on Grid 1 (`-0.98%`) and
  `2.60407 -> 2.49195 s` on Grid 2 (`-4.31%`). Grid 1 did not meet the
  optimistic 4% threshold, but both grids moved causally with fewer calls.
- R09 remained neutral/faster (`1.8825/5.6261 -> 1.8754/5.5200 s`). Profile
  total improved slightly `71.20 -> 71.10 s`; R44 also moved down and is not
  credited to this change.
- Independent validate job `118806937` passed. Its clean candidate was
  `Local_Lab/runs/validation/candidate_20260809T000809Z_8197`; the validation
  report passed with all checked errors within `1e-5`.

## Decision

Accept after the required independent validate. The change is exact, removes
real message starts, has no target or compute regression, and provides a small
approximately `0.1 s` score gain under the team's relaxed rule for logically
effective optimizations.
