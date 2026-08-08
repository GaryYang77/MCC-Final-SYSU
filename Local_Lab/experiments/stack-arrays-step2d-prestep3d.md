# Use stack automatic arrays only in R09 and R22 objects

- Accepted anchor: `be0600759b0685bcd48e1781cd0ce1b5caf98190`.
- Required reference run:
  `Local_Lab/runs/profile128/predictor-horizontal-k-order-4n64-16ppn_20260808T135659Z_14464`
  (job `118787413`; slow-allocation total `93.01 s`; all 26 comparisons
  bitwise zero).
- Secondary steady-state context:
  `Local_Lab/runs/profile128/tracer-horizontal-k-order-4n64-16ppn_20260808T130839Z_46165`
  (`79.75 s`), before the accepted predictor loop reorder.
- Targets: R09 and R22 on both grids. Secondary guard regions: R19 and R35.

## Evidence and falsifiable hypothesis

The rejected all-stack experiment (job `118787690`) was stack-safe and exact.
Against the steady context, R09 improved `6.9/6.0%` and R22 improved
`13.4/12.4%` on Grid 1/2, whereas R19 regressed `6.2/8.2%` and R35 regressed
`11.0/14.5%`. This opposing response falsified global removal of
`-heap-arrays`, but identifies a narrower storage-placement hypothesis.

Retain the global `-heap-arrays` default and filter it only from the compile
flags for `step2d.o` and `pre_step3d.o`. All competition Slurm entry points
already set unlimited stack. No equation, expression, CPP option, profiler,
input, MPI mapping, or precision changes.

Expected output is bitwise identical. Expected performance is lower R09/R22
on both grids relative to allocation-wide compute behavior, while R19/R35 no
longer show the all-stack regression. Build/stack failure, any nonzero output
comparison, absent target benefit, or recurring R19/R35 regression falsifies
the hypothesis.

## Result

- Clean PROFILE build: job `118787817`, candidate
  `Local_Lab/runs/validation/candidate_20260808T141958Z_10259`; build report
  passed and binary SHA-256 was
  `3571d33be688aeb9e9787817858426dcc595aee583e9deb9c90390c092635af3`.
- 4n64 score DEMO: job `118787917`, run
  `Local_Lab/runs/profile128/stack-arrays-step2d-prestep3d-4n64-16ppn_20260808T142714Z_24979`.
  It ended normally and passed every output/comparison gate; all 26 variables
  had `RMSE=0` and `max_abs=0`. Profile total was `77.95 s`, resource wall
  `80.06 s`, and max RSS `795612 KiB`.
- Against the `79.75 s` steady context, Grid-1/2 R09 changed from
  `1.913/5.726` to `1.848/5.570 s` (`-3.4/-2.7%`). R22 changed from
  `2.886/8.285` to `2.527/7.334 s` (`-12.4/-11.5%`), including the accepted
  predictor loop reorder. The guard regions no longer showed the all-stack
  regression: R19 was `-0.2/+1.3%`, and R35 `-0.3/+0.4%`. Calls were
  unchanged. Total improved `2.26%` despite volatile R03/R44.

Decision: accept. The object-specific flags reproduce the desired R09/R22
direction on both grids, isolate the adverse R19/R35 response, preserve exact
outputs, and remain stack/RSS safe.

Bundle:
`profile_bundle_logs/stack-arrays-step2d-prestep3d-4n64-16ppn_20260808T142714Z_profile_bundle.json`.
