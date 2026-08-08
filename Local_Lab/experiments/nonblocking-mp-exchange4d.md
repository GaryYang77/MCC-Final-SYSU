# Nonblocking sends in mp_exchange4d

Date: 2026-08-09

## Hypothesis

- Accepted parent: `b471bf1f7f046ebea467e1e8ea7d474d92118e42` (performance
  source `c76d25c`).
- Target: Grid 1/2 region 42, the four-dimensional halo exchange.
- Reference:
  `Local_Lab/runs/profile128/combine-t3dmix4-face-coefficients-4n64-16ppn_20260808T213949Z_52705`.
- `mp_exchange4d` posts both receives in a direction pair but then executes
  two blocking sends in sequence. Use nonblocking sends and defer their waits
  until after the matching receive buffers have been unpacked. This allows
  west/east, and separately south/north, transfers to progress concurrently
  with each other and with local unpack work.
- South/north packing intentionally remains after west/east receive and
  unpack: it reads the updated east/west ghosts to propagate corner values.
  Message contents, tags, peers, receive order, packing order, and unpacking
  order remain unchanged.
- Expected result: region 42 decreases by at least 5% with unchanged call
  counts and bitwise-identical values. Regions outside communication should
  not show a causal regression.

## Result

- Local gate: 53 tests passed; `git diff --check` passed.
- PROFILE build: job `118804741`, candidate
  `Local_Lab/runs/validation/candidate_20260808T221959Z_10371`, build report
  PASS; binary SHA-256
  `3044d068d05a7523803993c73c636c689ab32205d8dc6985b090e5c7793b8917`.
- 4n64 DEMO: job `118805000`, run
  `Local_Lab/runs/profile128/nonblocking-mp-exchange4d-4n64-16ppn_20260808T222611Z_22748`.
- Correctness: normal end, outputs/comparison PASS, and all 26 variables had
  `RMSE=0` and `max_abs=0`.
- Target result with unchanged call counts:
  - Grid 1 R42: `1.4896885 -> 1.4292800 s` (`-4.06%`), calls `23296`.
  - Grid 2 R42: `5.4891441 -> 5.1861829 s` (`-5.52%`), calls `76864`.
- Profile total: `71.59 -> 71.20 s`. Grid-2 R44 independently increased
  `1.37 -> 1.62 s`, while stable compute regions R35, R39 and R54 did not
  show an offsetting regression. GNU-time wall was `73.25 s`; it is not a
  no-profile phase score.
- Independent 1-rank validation: job `118805052`, candidate
  `Local_Lab/runs/validation/candidate_20260808T222921Z_500`, exit status 0,
  `[validate] PASS`, `validation_report.json passed=true`, and all 26
  file/variable metrics had zero error.

## Decision

Accepted. Nonblocking sends causally reduced the targeted R42 on both grids,
while preserving message contents/order, normal completion, and bitwise
results in both correctness gates. The DEMO run becomes the next score
reference.
