# Reuse GLS dissipation powers across implicit systems

- Accepted anchor: `0db324f4c64a45225a044d07f1126b4ac4910abd`.
- Reference: `reuse-tracer-vdiff-factorization-4n64-16ppn_20260806T030317Z_26389`.
- Target: Grid 2/1 region 19 (`7.880846/3.039504 s`).
- Evidence: the rejected broad K-kl algebra specialization cut region 19 by
  about 56%, proving that general power evaluation is material, but its
  reordered algebra exceeded the numerical gate. In the original corrector,
  the identical `gls**(-gls_exp1)` and `tke**tke_exp2` values are evaluated
  separately for the adjacent BCK and BCP matrix expressions at every point.
- Hypothesis: evaluate those two powers once, store them in scalar temporaries,
  and use the same values in both original multiplication sequences. All
  exponents, operations, matrix equations, and generic GLS paths are retained.
- Expected numerical behavior: bitwise-identical DEMO output, lower region 19
  and total wall. The main performance saving is two fewer general power
  evaluations per interior water-column point.
- Falsifier: any nonzero comparison metric or no useful region-19/total gain.

## Result: accepted

- Build job `118659752`; candidate
  `candidate_20260806T040103Z_30047`; binary SHA-256
  `75654998ef6eb8c90df14c3d96aea70b76c2a5cc845e8b636205ed9f26c2cac3`.
- DEMO job `118659853`, run
  `reuse-gls-dissipation-powers-4n64-16ppn_20260806T040749Z_25160`:
  normal end, complete outputs, and all 26 variables had
  `RMSE=0, max_abs=0`.
- Grid 1 region 19: `3.039504 -> 2.694895 s` (`-11.34%`). Grid 2
  region 19: `7.880846 -> 7.143901 s` (`-9.35%`).
- Observed total was `83.787181 s` versus `80.029315 s`, entirely confounded
  by an unrelated region-44 MPI broadcast increase: Grid 1/2 region 44 added
  `3.567760/0.987009 s`; non-target compute regions were stable. The same
  elevated broadcast behavior appeared across the preceding independent
  binaries, while the targeted compute reduction here was clear and the
  implementation cannot add communication.
- Triggered 1-rank validation job `118659914`, candidate
  `candidate_20260806T041102Z_8203`: `passed=true`, 26 reported metrics all
  had `RMSE=0, max_abs=0`; candidate wall `187.082 s` versus sealed baseline
  `188.695 s` (`-0.85%`).
