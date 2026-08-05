# Route fine-to-coarse block sums only to coarse receiver ranks

- Accepted anchor: `18bc7ed3d1186527bab5568205ef5220b5762974`
- Reference: `route-contact-to-receivers-4n64-16ppn_20260805T141157Z_33790`
- Target: Grid 2 region 49 (`13.866949 s`) inside region 55
  (`16.421346 s`).
- Hypothesis: the hybrid fine-to-coarse path computes each complete donor
  block sum on one fine-grid owner, yet its owner-aware Allgatherv replicates
  that record to all ranks. Only the rank containing the corresponding coarse
  contact consumes it. Cache that coarse receiver owner and use the accepted
  donor-to-receiver Alltoallv path for `Fsum`.
- Blocks crossing fine-grid tiles remain on the existing raw `Fcross`
  Allreduce/reconstruction path. Mask counts and all floating-point loops are
  unchanged.
- Expected numerical behavior: bitwise-identical output and unchanged region
  49 call count, with lower Grid 2 region 49/55 and total wall.
- Falsifier: DEMO comparison failure, abnormal termination, or clear total
  wall regression.

## Result

- Clean build job `118633697`, candidate
  `candidate_20260805T141811Z_27759`, binary SHA-256
  `36b3e24cdcd3b855bbdbd0c45a9bac32ce5373b1a2eb548c1e360eb29c18f2cc`.
- DEMO job `118633872`, run
  `route-fsum-to-receivers-4n64-16ppn_20260805T142405Z_33351`, completed
  normally with `passed=true`, `comparison.passed=true`, and all 26 variables
  at `RMSE=0`, `max_abs=0`.
- Grid 2 region 49 fell from `13.866949 s` to `12.547524 s` (`-9.51%`),
  region 55 from `16.421346 s` to `14.960544 s` (`-8.90%`), and region 39
  from `20.476270 s` to `18.988438 s` (`-7.27%`). Call counts were unchanged.
- Profile total mean changed from `90.332585 s` to `90.546649 s` (`+0.24%`)
  and Slurm wall from `92.21 s` to `92.35 s`, neutral at single-run noise
  resolution. Peak RSS fell from `816268` to `788060 KiB` (`-3.46%`).

Decision: accept under the team's relaxed rule. The targeted path improves
materially, memory improves, output is bitwise exact, and total wall has no
clear regression. Do not claim an additional cumulative total speedup from
this single measurement.
