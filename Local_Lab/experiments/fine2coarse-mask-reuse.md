# Fine-to-coarse 3D mask-reuse experiment

- Accepted commit / rollback anchor: `ff7888969c4fbccd07850142a15d256a4d7d5e65`
- Branch: `perf/fine2coarse-mask-reuse`
- Accepted reference: `Local_Lab/runs/profile128/ticket-861-vweights-2n64_20260804T092249Z_53627`
- Reference binary SHA-256: `4dad6d9476b31a50ab0d8d5f20744ac04d63963953e438e88107cb0119f8771f`

## Falsifiable hypothesis

Grid 2 region 46 takes 58.97 seconds and records 171584 aggregate calls across
ranks in the accepted 2-node DEMO. `fine2coarse3d` aggregates the same dynamic
rho wet/dry mask separately for each of the 10 consecutive tracers even though
model time and wet/dry state cannot change inside that tracer loop.

Refresh the global rho mask for the first tracer and reuse it for the remaining
nine tracers in the same `fine2coarse(r3dvar)` section. Momentum masks continue
to be refreshed independently, and the first tracer refreshes the rho mask on
every coupling section, so no mask is reused across a `WET_DRY` update.

The change should remove 9 collectives per coupling section, reducing Grid 2
region 46 calls and decreasing region 46 wall. All 26 file/variable comparisons
must remain bitwise identical; profiling sources and inputs must not change.

## First run

- Local tests: 42 passed; MPI and serial preprocessed interfaces checked.
- Validation: job `118544103`, candidate
  `candidate_20260804T094450Z_14782`, binary SHA-256
  `29801665aa9d49ec7cb1b7f7e64f52c25019d10e0a625a35d774f8f28d8b3eef`;
  wrapper exit zero, `[validate] PASS`, and `passed=true`.
- Profiling: job `118544521`, run
  `fine2coarse-mask-reuse-2n64_20260804T095359Z_41304`; `passed=true`,
  `normal_end=true`, `comparison.passed=true`, and all 26 comparisons have
  `RMSE=0`, `max_abs=0`.
- Grid 2 region 46 calls fell from 171584 to 110144. Region 46 wall fell from
  58.97 to 57.04 seconds and region 55 fell from 60.35 to 58.55 seconds.
- Total wall changed from 239.95 to 248.64 seconds (+3.62 percent). Grid 1
  region 49 rose from 46.75 to 48.39 seconds and Grid 2 region 49 rose from
  4.97 to 5.86 seconds.

The communication-count reduction and bitwise correctness establish that the
logic works, but one total-wall sample is inconclusive. Per the team's revised
acceptance policy, run one independent DEMO repeat against the same accepted
reference before deciding whether the total regression is persistent.

## Repeat and decision

- Validation was repeated after reconstructing the source: job `118545464`,
  candidate `candidate_20260804T100612Z_4279`, binary SHA-256
  `c1dedc4fdafc71fab250e30d4fd4d768c4ba304f0884633e6a85189888aaa116`;
  wrapper exit zero, `[validate] PASS`, and `passed=true`.
- Independent profiling repeat: job `118546479`, run
  `fine2coarse-mask-reuse-repeat-2n64_20260804T101540Z_55922`;
  `passed=true`, `normal_end=true`, `comparison.passed=true`, and all 26
  comparisons again have `RMSE=0`, `max_abs=0`.
- The repeat reproduced the logical effect: Grid 2 region 46 calls remained
  at 110144, region 46 was 56.36 seconds, and region 55 was 58.33 seconds.
  The accepted reference values are 171584 calls, 58.27 seconds, and 60.25
  seconds respectively.
- Slurm wall was 245.56 seconds in the repeat (+2.34 percent versus the
  239.95-second accepted reference); the first run was 248.64 seconds (+3.62
  percent). Model profile totals show the same direction: 243.12 seconds in
  the repeat versus 237.63 seconds in the reference.

Decision: tentatively accept under the team's revised policy. The eliminated
collectives are logically redundant within one tracer loop, the target effect
is repeatable, and correctness is bitwise identical. The 2.34--3.62 percent
total-wall headwind is recorded rather than hidden; retain the original
ticket-861 run as a historical anchor and reassess this commit in a later
cumulative A/B candidate. If the headwind persists after larger gains are
combined, revert this isolated commit.
