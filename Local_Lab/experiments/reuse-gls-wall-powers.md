# Reuse GLS wall-function powers

- Accepted anchor: `11f077bd7a84e8d805a5dca8f4e6ccf07b0bd1d9`.
- Reference: `reuse-gls-dissipation-powers-4n64-16ppn_20260806T040749Z_25160`.
- Target: Grid 2/1 region 19 (`7.143901/2.694895 s` in the accepted run).
- Hypothesis: the active `Lmy25` parabolic wall function evaluates identical
  `gls**gls_exp1` and `tke**(-tke_exp1)` powers independently for its bottom
  and free-surface corrections at every interior point. Compute each original
  power once and reuse it in both unchanged multiplication sequences.
- No exponent is specialized and the generic non-`Lmy25` path is untouched.
  Equations, coefficients, depth factors, boundaries, and MPI are unchanged.
- Expected numerical behavior: bitwise-identical outputs, lower region 19 and
  total wall through two fewer general power evaluations per interior point.
- Falsifier: any nonzero comparison metric or no useful region-19/total gain.

## Result: accepted

- Build job `118660148`; candidate
  `candidate_20260806T042834Z_22832`; binary SHA-256
  `a84fb1e31ce11d16ba92d574424bd5a7559deafff3a042477eb83f1d9da726d1`.
- DEMO job `118660248`, run
  `reuse-gls-wall-powers-4n64-16ppn_20260806T043445Z_52399`: normal end,
  complete outputs, and all 26 variables had `RMSE=0, max_abs=0`.
- Grid 1 region 19: `2.694895 -> 2.523300 s` (`-6.37%`). Grid 2
  region 19: `7.143901 -> 6.568037 s` (`-8.06%`). Total improved from
  `83.787181 s` to `81.892702 s` (`-2.26%`).
- Triggered 1-rank validation job `118660312`, candidate
  `candidate_20260806T043746Z_11487`: `passed=true`; 26 reported metrics all
  had `RMSE=0, max_abs=0`. Candidate wall was `160.240 s` versus sealed
  baseline `188.695 s`; this single 1-rank timing is supporting evidence, not
  the primary DEMO performance measurement.
