# Cache t3dmix4 tracer-independent coefficients

Date: 2026-08-09

## Hypothesis

- Accepted parent: `f81fd1d` (performance source `d68e187`).
- Target: Grid 1/2 region 27, biharmonic tracer mixing on S-surfaces.
- Current reference: `Local_Lab/runs/profile128/cache-c4-transport-halves-4n64-16ppn_20260808T200411Z_51013`.
- The active `DIFF_3DCOEF && TS_U3ADV_SPLIT` path recomputes the same
  `0.5*diff3d_{u,v}*metric` factors and `Hz` face sums for every tracer and
  both harmonic operators. Cache them once per call and reuse them without
  changing either harmonic operator or the tracer update arithmetic.
- Expected result: region 27 decreases by 8--15% with unchanged call counts;
  all 26 comparison variables remain bitwise identical. Other compute and
  nesting regions should not regress materially.

## Result

- Local gate: `/tmp/mcc-validation-venv/bin/python -m pytest -q Local_Lab/tests`,
  53 passed.
- PROFILE build: job `118803017`, candidate
  `Local_Lab/runs/validation/candidate_20260808T210337Z_32344`, build report
  PASS, binary SHA-256
  `31f788d8f30a95677b939ec4afaac4a1399a37b13c0c3ade5f6581a4977617dd`.
- 4n64 DEMO: job `118803141`, run
  `Local_Lab/runs/profile128/cache-t3dmix4-coefficients-4n64-16ppn_20260808T211002Z_63841`.
  The SSH submitter disconnected after Slurm submission, so the completed
  output was finalized with the unchanged `profile_128.finalize_report`
  function rather than rerunning the model.
- Correctness: normal end, output inspection PASS, all 26 comparison
  variables had `RMSE=0` and `max_abs=0`.
- Target result:
  - Grid 1 R27: `1.1400482 -> 0.9729853 s` (`-14.65%`).
  - Grid 2 R27: `2.9821716 -> 2.3967872 s` (`-19.63%`).
  - Calls remained `3904` and `19200`, respectively.
- Profile total: `72.41 -> 71.65 s` (about `-1.05%`). The target-region
  reduction accounts for essentially all of this improvement. R44 and MPI
  regions retained their known allocation-dependent variation.
- GNU-time wall: `74.86 -> 73.97 s`; reported maximum RSS did not increase
  (`797852 -> 791792 KiB`).
- Independent 1-rank validation: job `118803276`, candidate
  `Local_Lab/runs/validation/candidate_20260808T211526Z_28054`, Slurm
  COMPLETED with exit code 0. `validation_report.json` passed and all 26
  file/variable metrics had `RMSE=0` and `max_abs=0`; the model ended with
  `ROMS/TOMS: DONE`.

## Decision

Accepted. The causal R27 improvement, bitwise 4n64 DEMO comparison, and
independent 1-rank validation satisfy every applicable gate. This run becomes
the reference for the next experiment.
