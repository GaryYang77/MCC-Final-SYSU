# Skip unit U/V masks in all-wet predictor tiles

## Hypothesis

- Accepted commit: `cb520b787b5914c04931d9384cb46b91bf3352e3`.
- Reference run: `Local_Lab/runs/profile128/tracer-all-wet-horizontal-mask-4n64-16ppn_20260809T015113Z_31317`.
- Grid 2 is fully wet.  In `pre_step3d`, the high-order horizontal tracer
  predictor nevertheless reloads and multiplies static unit U/V masks for
  every vertical level and tracer.  Scanning each mask footprint once per
  predictor call and retaining the original masked loop for mixed tiles removes
  redundant unit multiplications without changing loop order or any value.
- Target: lower Grid-2 R22 (`3d_equations_predictor`) with unchanged calls;
  Grid 1 should be neutral or slightly lower.  Guard R09, R19, R35, R39, R44,
  R49, R54 and R55.
- Reject on abnormal completion, missing output, any nonzero comparison, or no
  causal R22 improvement.

## Result

- Build job `118811028`; candidate
  `candidate_20260809T034517Z_16798`; binary SHA-256
  `6f785b6f81a67e10d100016bc432b585a77e195590d2e853fa2425f5cbb166d3`.
- 4n64 DEMO job `118811092`; run
  `predictor-all-wet-horizontal-mask-4n64-16ppn_20260809T035110Z_60524`.
  It ended normally and all 26 variables were bitwise identical.
- R22 calls were unchanged.  Grid 1 R22 fell `2.471720 -> 2.459875 s`
  (`-0.48%`); fully wet Grid 2 fell `7.218761 -> 7.100594 s`
  (`-1.64%`).  Profile total was `70.18 s`; several guard compute regions
  were also slightly faster, so only the structurally larger Grid-2 R22 delta
  is attributed to this change.
- Triggered 1-rank validation job `118811117`, candidate
  `candidate_20260809T035419Z_14472`, passed with all RMSE and max-absolute
  errors within `1e-5`.
- **Accepted.**  Evidence bundle:
  `profile_bundle_logs/predictor-all-wet-horizontal-mask-4n64-16ppn_20260809T035110Z_profile_bundle.json`.
