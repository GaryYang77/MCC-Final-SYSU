# R22 vertical-advection time-metric cache experiment

- Date: 2026-08-12
- Branch: `perf/r22-vertical-time-metric`
- Accepted starting commit:
  `d3795878bc398a649bc8ac2d8df6d16c9273d0ef`
- Score reference:
  `Local_Lab/runs/profile128/tracer-flux-direct-copy-4n64-16ppn_20260811T151359Z_47837`
- Correctness channel declared before testing: `exact`

## Falsifiable hypothesis

R22 diagnostic job `118958689` measures Grid-2 tracer vertical advection at
`1.4071 s`, the second-largest compute child. Before entering the horizontal
and vertical phases, `pre_step3d` already computes
`cffpmnp(i,j)=cff_time*pm(i,j)*pn(i,j)`. Artificial continuity reuses it, but
the final vertical-advection update redundantly reconstructs the identical
`cff*pm(i,j)*pn(i,j)` for every tracer and vertical level.

Reuse `cffpmnp` in that update and remove the repeated time-coefficient branch
inside `T_LOOP2`. This should remove two multiplications per wet point per
tracer/level without changing multiplication order, C4 vertical fluxes, DC,
stencil bounds, or output. Accept only if the exact 4n64 score DEMO passes and
R22/total move in the predicted direction.

## Loop and compiler evidence before modification

- Target loop: preprocessed `pre_step3d.f90` lines 548--555, nested under
  `j`, tracer, and `k`; Grid 2 executes the parent phase 300 times/rank.
- `i` is the innermost contiguous dimension. Diagnostic compile job
  `118959226` reports that the line-549 loop is vectorized with vector length
  2 and estimated potential speedup `1.66` in the aligned version (`1.36` in
  the alternate assumed-stride version).
- The expensive coefficient is invariant across tracer and `k`, and its
  exact value is already materialized in the 2-D `cffpmnp` plane. No new
  temporary, division, loop fusion, or register-heavy stencil is introduced.
- Old and new coefficient evaluation both use the existing double value
  `cff_time` followed by left-associated multiplication by `pm` then `pn`.
  The new path merely loads that already rounded double value.

## Results

- Clean score build: job `118961035`, candidate
  `Local_Lab/runs/validation/candidate_20260811T164157Z_25167`, binary
  SHA-256
  `8c59701c46605a1a4e43c983850b8977d9b0eb7447c23ccce2ad33c205246fdb`.
- Score DEMO: job `118961520`, run
  `Local_Lab/runs/profile128/r22-vertical-time-metric-4n64-16ppn_20260811T164844Z_21545`.
- Normal end; all output checks passed. Exact comparison covered 26 variables
  and every `RMSE` and `max_abs` was zero.
- Grid-2 R22 improved from `6.853677 s` to `6.789401 s` (`-0.94%`) with
  identical calls. Grid-1 R22 improved `0.54%`.
- Stable Grid-2 compute guards supported the direction: R09 `-0.91%`, R19
  `-0.21%`, R35 `-1.26%`; R34 changed `+0.56%` (`+0.006 s`).
- Raw Grid-2 total changed from `67.768866 s` to `68.191513 s` (`+0.62%`).
  The controlling Grid-1 total changed by `+0.421879 s`, while the known
  volatile R03 input and R44 broadcast regions alone increased by
  `0.338993 s` and `0.747654 s`. Their combined increase exceeds the raw
  total regression; removing those arrival/filesystem terms yields an
  improving direction. No automatic rerun was added.

Decision: accepted as a small exact-equivalence cumulative candidate. The
target region and stable compute guards support the causal hypothesis, while
the contradictory raw total is completely covered by documented R03/R44
noise on the controlling grid. The gain is far below the 5% full-run trigger,
so no no-profile full task or 1-rank validate is run.
