# Load tracer RHS directly during vertical-diffusion solve

- Accepted anchor: `9fc7262c190864b81a275b9c3b26424d123ba1ac`.
- Reference: `Local_Lab/runs/profile128/f2c-sparse-peer-assemble-rerun-4n64-16ppn_20260807T131759Z_62443`
  (job `118738160`, 4n64/16ppn, `8x8`, 60/300; resource wall
  `78.94 s`; all 26 comparisons bitwise zero).
- Target: tracer corrector region 35, specifically the implicit vertical
  diffusion solve in `step3d_t.F`.
- Evidence: Intel 17 no-IPO loop/vector report from compile job `118740773`
  shows that the inner `i` loops are already vectorized. The remaining code
  first copies every vertical RHS value from `t` to `DC`, then immediately
  overwrites `DC` during forward substitution.
- Hypothesis: read each RHS value directly from `t` when computing its
  forward-substituted `DC` value, eliminating the full `t -> DC` copy pass
  without changing any floating-point multiplication, subtraction, division,
  or their order.
- Scope: `ROMS_CoSiNE15/ROMS/Nonlinear/step3d_t.F`, non-`SPLINES_VDIFF`
  vertical diffusion branch only. Profiling, physics, coefficients, MPI,
  precision, inputs, and loop bounds remain unchanged.
- Expected numerical behavior: bitwise-identical outputs; lower Grid 1/2 R35
  and total wall; unchanged call counts and non-tracer regions.
- Falsifier: build failure, any nonzero comparison error, or no useful R35/total
  improvement.

## Result

Accepted.

- Clean PROFILE candidate:
  `Local_Lab/runs/validation/candidate_20260807T150743Z_23228`, build job
  `118741038`, `build_report.passed=true`, binary SHA-256
  `bdc63f3eea29ff2677316656eb5d7115e67f6ce1b043f07448cb544e167ebc18`.
- DEMO job `118741183`, run
  `tracer-vdiff-direct-rhs-4n64-16ppn_20260807T151528Z_54133`: normal end,
  outputs/profile present, and all 26 comparisons have
  `RMSE=0, max_abs=0`.
- Resource wall improved `78.94 -> 78.40 s` (-0.68%); Grid 2 profiler total
  improved `76.915478 -> 76.485449 s` (-0.56%).
- Target R35 improved on both grids: Grid 1
  `3.1406240 -> 3.1324561 s` (-0.26%) and Grid 2
  `9.3433077 -> 9.2857266 s` (-0.62%). Calls and numerical behavior were
  unchanged.

The gain is small but directionally consistent with removing one full RHS
copy pass, and total performance improved. Accept this candidate as the next
reference.
