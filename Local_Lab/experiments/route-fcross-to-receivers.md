# Route crossing-block cells to receiver ranks

- Accepted anchor: `6b52c2939fa84368de2b374525d3fca2607ace9e`
- Reference: `cache-local-receiver-index-4n64-16ppn_20260805T144015Z_10381`
- Targets: Grid 2 region 49 (`12.537650 s`) and region 55
  (`15.038908 s`).
- Hypothesis: the remaining crossing fine-to-coarse blocks use a full-array
  `MPI_Allreduce`, although each horizontal cell has exactly one donor owner
  and each coarse contact has exactly one receiver rank. Cache the cell-owner
  map and send each vertical record only from its owner to that receiver with
  `MPI_Alltoallv`.
- The packed order is deterministic (`contact`, horizontal cell, vertical
  level), and the receiver reconstructs the same order independently for each
  source rank. No floating-point values are combined: this replaces a sum of
  one owned value and zeros with an exact copy of that owned value.
- Complete-block Fsum, masks, interpolation, averaging order, generic
  aggregation, and non-`DISTRIBUTE` paths are unchanged.
- Expected numerical behavior: bitwise-identical output and lower Grid 2
  region 49/55 and total wall.
- Falsifier: DEMO comparison failure, missing cell ownership, or clear
  total-wall regression.

## Result

- Build job: `118634376`
- Candidate: `candidate_20260805T144954Z_12801`
- Binary SHA-256:
  `f389862d1a9d0c62603cd789bd6afebabbd9e17625e716408897d36af0f6f612`
- Profile job: `118634485`
- Run: `route-fcross-to-receivers-4n64-16ppn_20260805T145632Z_51111`
- Correctness: PASS; normal end and complete outputs; all 26 comparisons have
  `RMSE == 0` and `max_abs == 0`.
- Total profile mean: `90.031064 -> 80.282807 s` (`-10.83%`).
- Grid 2 region 49: `12.537650 -> 3.430675 s` (`-72.64%`).
- Grid 2 region 55: `15.038908 -> 5.919295 s` (`-60.64%`).
- Grid 2 region 39: `19.089710 -> 9.966575 s` (`-47.79%`).
- Maximum RSS: `795124 -> 790412 KiB` (`-0.59%`).

Accepted. Relative to the phase-two starting reference (`117.744595 s`), the
cumulative DEMO profile mean is now `31.81%` lower and passes the 30% target.
