# Cache fine-to-coarse donor-block map

- Accepted anchor: `ea223a66ca9f1d45b809111a8b313e386ea02374`
- Reference: `no-inactive-massflux-diagnostic-4n64-16ppn_20260805T125043Z_40398`
- Target: Grid 2 region 55 (`fine2coarse3d`), 16.72 s mean wall.
- Hypothesis: the donor-block owner and crossing-slot maps depend only on the
  fixed contact geometry and MPI decomposition, but are allocated and rebuilt
  for every 3-D state variable. Building each R/U/V contact map on first use
  and retaining it removes repeated `Npoints * Nranks` integer scans and small
  allocations without changing any floating-point operation or communication.
- Expected numerical behavior: bitwise-identical output.
- Falsifier: DEMO comparison failure or a clear total-wall regression.

## Result

- The first two clean-build submissions exposed and then localized an
  `INTENT(IN)` declaration edit applied to the adjacent 2-D routine. Neither
  attempt ran the model. The corrected clean build was job `118632631`,
  candidate `candidate_20260805T132659Z_15213`, binary SHA-256
  `ade107addfbac5fef6964ef656a5af6735079182b9b8cf5e5debc3cbd8cc4880`.
- DEMO job `118632735`, run
  `cache-fine2coarse-block-map-4n64-16ppn_20260805T133300Z_62076`, completed
  normally with `passed=true` and `comparison.passed=true`. All 26 variable
  comparisons have `RMSE=0` and `max_abs=0`.
- Profile total mean fell from `104.43012 s` to `102.69084 s` (`-1.67%`),
  and Slurm wall fell from `106.36 s` to `104.70 s`.
- Grid 2 region 55 fell from `16.718636 s` to `15.977938 s` (`-4.43%`).
  Grid 2 region 39 fell from `20.837023 s` to `20.082838 s`; its call count
  was unchanged. Peak RSS rose only from `813012` to `816044 KiB` (`+0.37%`).

Decision: accept. The cache eliminates repeatable integer work and allocation
from the intended hotspot, improves total wall, and is bitwise identical.
