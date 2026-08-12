# R27 second-harmonic all-wet face fast path

Date: 2026-08-12

## Hypothesis

- Accepted parent: `4de4b54213badc4996148f2567ef559efc12647d`;
  accepted model source: `c13df28dd03b98af69a1a435049e31d04862ee85`.
- Reference:
  `Local_Lab/runs/profile128/r27-first-harmonic-all-wet-4n64-16ppn_20260811T235556Z_44686`.
- Target: R27 second harmonic face fluxes. Diagnostic job `118986594`
  measured site 248 at `0.8205 s` on Grid 2, 35.9% of its then R27 parent.
- Reuse the accepted per-direction `LallWetU/LallWetV` result. Fully wet
  directions skip only two final multiplications by exact one; any non-unit
  face retains the original loop and operation order. No new scan or array.

## Result

- Model commit: `477e430a25d55034ca7968cd7d737406fdcc6f16`.
- Local gate: 82 tests and `git diff --check` passed.
- PROFILE build job `118988209`, candidate
  `Local_Lab/runs/validation/candidate_20260812T001636Z_19716`, PASS;
  binary SHA-256
  `f1572f9b57e773bd1a7644e30e7541d57fa5cebcc100b9cda0ffab75c7068f80`.
- Single score DEMO job `118988636`, run
  `Local_Lab/runs/profile128/r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_53023`.
  Normal end, output inspection PASS, and all 26 comparisons exact.
- Grid-2 R27: `1.8905753 -> 1.6553296 s` (`-12.44%`); Grid-1 R27:
  `0.8418022 -> 0.8164574 s` (`-3.01%`). Calls remained unchanged.
- GNU-time wall: `70.16 -> 68.72 s` (`-2.05%`). R03/R44 were also
  favorable in this allocation and are not credited to source; R27 itself is
  the causal acceptance signal.
- Candidate compiler job `118988800` confirmed the all-wet second-pass loops
  remain VL2-vectorized and reduce scalar/vector cost from `25/13.5` to about
  `9/5`; original mask loops remain. Report SHA-256:
  `ee7b5c3e5382c0e287288212349f2348d6c565c24defb3023e783c30c126980a`.
- Triggered validate job `118988820` exited zero with `[validate] PASS`; all
  26 metrics were exact. Report SHA-256:
  `1642982a1bebdfd57300f7f493dea0c8aa07d6f1982cab2ebaba16ae96b00c2f`.

## Decision

Accepted. The run becomes the next score reference. Relative to the pre-R27
reference, the two accepted R27 changes reduce DEMO wall `72.02 -> 68.72 s`
(`-4.58%`), still below the 5% full-run trigger; no 4n96/full job was run.

Evidence bundle:
`profile_bundle_logs/r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_profile_bundle.json`.
