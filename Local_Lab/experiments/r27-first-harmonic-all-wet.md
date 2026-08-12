# R27 first-harmonic all-wet face fast path

Date: 2026-08-12

## Hypothesis

- Accepted infrastructure parent: `94ad026b3f3f8864a7b060e542ce1e33b778969a`;
  accepted model parent: `818523ed0c845729ebaa72ea148c00dc6a965d12`.
- Target: Grid-2 R27 first harmonic tracer face fluxes. Diagnostic job
  `118986594` measured this phase at `1.3787 s`, 60.4% of R27.
- Accepted compile-only job `118986912` showed both U/V face loops already
  vectorized at vector length 2, but with four emulated non-unit-stride loads
  including the static and wet/dry face masks.
- Exact hypothesis: detect once per tile call whether every U or V face used
  by the first harmonic has both masks exactly equal to one. A fully wet
  direction skips only the two unit multiplications; any non-unit face keeps
  the original loop and arithmetic for that entire direction.
- Expected result: Grid-2 R27 falls 5--10%, calls and all 26 outputs remain
  exact. No stencil, coefficient, timestep, mask value, or output changes.

## Result

- Model commit: `c13df28dd03b98af69a1a435049e31d04862ee85`.
- Local gate: 82 tests passed; `git diff --check` passed.
- PROFILE build: job `118987097`, candidate
  `Local_Lab/runs/validation/candidate_20260811T234920Z_9142`, report PASS,
  binary SHA-256
  `196f1d894c6195a7d3609f92d5262cea9d32e85fe75f9eebd59594762c7b6716`.
- Single 4n64 score DEMO: job `118987411`, run
  `Local_Lab/runs/profile128/r27-first-harmonic-all-wet-4n64-16ppn_20260811T235556Z_44686`.
  Normal end, output inspection PASS, and all 26 exact comparisons had
  `RMSE=0` and `max_abs=0`.
- Grid-2 R27: `2.2506630 -> 1.8905753 s` (`-16.00%`); Grid-1 R27:
  `0.8654814 -> 0.8418022 s` (`-2.74%`). Calls remained `19200/3904`.
- GNU-time wall: `72.02 -> 70.16 s` (`-2.58%`). Grid-2 R09/R35 moved
  `+4.52%/+2.38%`, while R03/R44 also had adverse arrival/filesystem movement;
  these partially mask the causal R27 gain and are not attributed to source.
- Candidate compile-only job `118987588` confirmed the all-wet loops remain
  VL2-vectorized, reduce emulated non-unit-stride loads from four to two, and
  reduce scalar/vector cost from `20/14` to `9/6`; the original mask path
  remains present. Local report SHA-256:
  `1c504087133282dc73249cad24760e853a65acca1264463df066d0bec773cb0c`.
- Triggered independent validate job `118987606` exited zero with
  `[validate] PASS`; all 26 metrics were exact. Report SHA-256:
  `028f3f0faf0e5007b0e03cf90f44174b7d50e5bde0bfd5ce28b51c29de2234eb`.

## Decision

Accepted. The exact output, target-region reduction, compiler evidence, lower
total wall, and independent mask-path validation satisfy the gate. The run
becomes the next 4n64 score reference. Its total improvement is only 2.58%,
below the 5% full-run trigger, so no 4n96 or full three-day job was submitted.

Evidence bundle:
`profile_bundle_logs/r27-first-harmonic-all-wet-4n64-16ppn_20260811T235556Z_profile_bundle.json`.
