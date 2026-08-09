#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

profile_binary=Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214/oceanM
reference_run=Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482
profile_sha=d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220

test -x "$profile_binary"
test -d "$reference_run"
printf '%s  %s\n' "$profile_sha" "$profile_binary" | sha256sum -c -

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

stage_run() {
  local label=$1
  python - "$profile_binary" "$label" <<'PY'
import sys
from pathlib import Path
from Local_Lab.profile_128 import stage_run

binary, label = sys.argv[1:]
run = stage_run(
    Path(binary).resolve(),
    label=label,
    outer_steps=60,
    inner_steps=300,
    tiles_i=12,
    tiles_j=8,
    nodes=4,
    ranks=96,
    preserve_output_cadence=False,
)
print(run)
PY
}

stamp=$(date -u +%Y%m%dT%H%M%SZ)
control_a=$(stage_run "rank-map-control-a-${stamp}")
mapped_a=$(stage_run "rank-map-i-stripe-a-${stamp}")
mapped_b=$(stage_run "rank-map-i-stripe-b-${stamp}")
control_b=$(stage_run "rank-map-control-b-${stamp}")

echo "[rank-map] control_a=$control_a"
echo "[rank-map] mapped_a=$mapped_a"
echo "[rank-map] mapped_b=$mapped_b"
echo "[rank-map] control_b=$control_b"

mkdir -p Local_Lab/cluster_logs
set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_CONTROL_A=${control_a},MCC_MAPPED_A=${mapped_a},MCC_MAPPED_B=${mapped_b},MCC_CONTROL_B=${control_b}" \
  -o "$mapped_a/rank_map_slurm_%j.out" \
  -e "$mapped_a/rank_map_slurm_%j.err" \
  Local_Lab/4n96_12x8_rank_map_abba.sbatch)
job_status=$?
set -e
job_id=${submission%%;*}
echo "[rank-map] job_id=$job_id exit_status=$job_status"
test "$job_status" -eq 0

python - \
  "$control_a" "$mapped_a" "$mapped_b" "$control_b" \
  "$profile_binary" "$reference_run" "$job_id" <<'PY'
import json
import sys
from pathlib import Path

from Local_Lab.profile_128 import elapsed_seconds, finalize_report

control_a, mapped_a, mapped_b, control_b = map(Path, sys.argv[1:5])
binary = Path(sys.argv[5])
reference = Path(sys.argv[6])
job_id = sys.argv[7]
common = dict(
    binary_source=binary,
    job_id=job_id,
    job_status=0,
    outer_steps=60,
    inner_steps=300,
    nodes=4,
    ranks=96,
    tiles_i=12,
    tiles_j=8,
    expect_profile=True,
    preserve_output_cadence=False,
    expect_diagnostics=False,
)

reports = {}
for name, run, compare_to in (
    ("control_a", control_a, reference),
    ("mapped_a", mapped_a, control_a),
    ("mapped_b", mapped_b, control_a),
    ("control_b", control_b, control_a),
):
    reports[name] = finalize_report(run, reference_run=compare_to, **common)

summary = {
    "schema_version": 1,
    "passed": all(report["passed"] for report in reports.values()),
    "job_id": job_id,
    "same_allocation": True,
    "order": ["control_a", "mapped_a", "mapped_b", "control_b"],
    "nodes": 4,
    "ranks": 96,
    "ranks_per_node": 24,
    "tiles_i": 12,
    "tiles_j": 8,
    "runs": {
        name: {
            "run_dir": str(run),
            "elapsed_wall_seconds": elapsed_seconds(run / "resource.log"),
            "passed": reports[name]["passed"],
        }
        for name, run in (
            ("control_a", control_a),
            ("mapped_a", mapped_a),
            ("mapped_b", mapped_b),
            ("control_b", control_b),
        )
    },
}
summary_path = mapped_a / "rank_map_abba_report.json"
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if not summary["passed"]:
    raise SystemExit(1)
PY

echo "[rank-map] PASS"
echo "[rank-map] mapped_a=$mapped_a"
echo "[rank-map] report=$mapped_a/rank_map_abba_report.json"

