# Cache locally consumed receiver contact indices

- Accepted anchor: `249df26ff0d697abee4eefe0e79f935b89ca00f5`
- Reference: `route-fsum-to-receivers-4n64-16ppn_20260805T142405Z_33351`
- Targets: Grid 2 region 54 (`4.049009 s`) and the receiver write-back part
  of region 55 (`14.960544 s`).
- Hypothesis: receiver ownership is now cached for targeted communication,
  but `put_contact2d/3d` and fine-to-coarse write-back still scan every contact
  point on every rank before rejecting non-local points. Cache each rank's
  ascending receiver index list when building `Rowner` and iterate that list.
- The original bounds checks remain in place. Communication, interpolation,
  arithmetic expressions, and contact order within each rank are unchanged.
  Paths where receiver ownership has not been constructed retain the full
  scan.
- Expected numerical behavior: bitwise-identical output, lower region 54/55
  and total wall.
- Falsifier: DEMO comparison failure or clear total-wall regression.

## Result

- Build job: `118634107`
- Candidate: `candidate_20260805T143422Z_29419`
- Binary SHA-256:
  `807e56a1fbef7532b26dee583321a3c2a732a89e606b878ea01975010bc07020`
- Profile job: `118634219`
- Run: `cache-local-receiver-index-4n64-16ppn_20260805T144015Z_10381`
- Correctness: PASS; normal end and complete outputs; all 26 comparisons have
  `RMSE == 0` and `max_abs == 0`.
- Total profile mean: `90.546649 -> 90.031064 s` (`-0.57%`).
- Grid 2 region 54: `4.021761 -> 4.044899 s` (`+0.58%`).
- Grid 2 region 55: `14.960544 -> 15.038908 s` (`+0.52%`).

The per-region changes are noise-sized and do not demonstrate a measurable
hotspot reduction. Accepted as a strictly equivalent local-index cache with no
clear total regression under the team's relaxed acceptance rule; the apparent
`0.57%` total improvement is not claimed as a stable speedup.
