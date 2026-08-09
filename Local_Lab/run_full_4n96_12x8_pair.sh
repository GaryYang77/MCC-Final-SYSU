#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

profile_binary=Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214/oceanM
control_binary=Local_Lab/runs/profile128/final-fastnodes-full-noprofile-4n96_20260809T095958Z_26214/oceanM
short_reference=Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482
full_reference=Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214
profile_sha=d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220
control_sha=fe0049c067b8a0efec3385c49dd9e606001d91444f7fcf176990a9f8f99f9c1e
preflight_limit=${MCC_PREFLIGHT_MAX_SECONDS:-90}

test -x "$profile_binary"
test -x "$control_binary"
test -d "$short_reference"
test -d "$full_reference"
printf '%s  %s\n' "$profile_sha" "$profile_binary" | sha256sum -c -
printf '%s  %s\n' "$control_sha" "$control_binary" | sha256sum -c -

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

stage_run() {
  local binary=$1
  local label=$2
  local outer_steps=$3
  local inner_steps=$4
  local preserve=$5
  python - "$binary" "$label" "$outer_steps" "$inner_steps" "$preserve" <<'PY'
import sys
from pathlib import Path
from Local_Lab.profile_128 import stage_run

binary, label, outer_steps, inner_steps, preserve = sys.argv[1:]
run = stage_run(
    Path(binary).resolve(),
    label=label,
    outer_steps=int(outer_steps),
    inner_steps=int(inner_steps),
    tiles_i=12,
    tiles_j=8,
    nodes=4,
    ranks=96,
    preserve_output_cadence=preserve == "yes",
)
print(run)
PY
}

stamp=$(date -u +%Y%m%dT%H%M%SZ)
preflight_run=$(stage_run "$control_binary" "final-12x8-preflight-${stamp}" 60 300 no)
control_run=$(stage_run "$control_binary" "final-12x8-full-noprofile-${stamp}" 2592 12960 yes)
profile_run=$(stage_run "$profile_binary" "final-12x8-full-profile-${stamp}" 2592 12960 yes)

echo "[full-pair] preflight_run=$preflight_run"
echo "[full-pair] control_run=$control_run"
echo "[full-pair] profile_run=$profile_run"

mkdir -p Local_Lab/cluster_logs
set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_PREFLIGHT_RUN_DIR=${preflight_run},MCC_CONTROL_RUN_DIR=${control_run},MCC_PROFILE_RUN_DIR=${profile_run},MCC_PREFLIGHT_MAX_SECONDS=${preflight_limit}" \
  -o "$profile_run/pair_slurm_%j.out" \
  -e "$profile_run/pair_slurm_%j.err" \
  Local_Lab/full_4n96_12x8_pair.sbatch)
job_status=$?
set -e
job_id=${submission%%;*}
echo "[full-pair] job_id=$job_id exit_status=$job_status"

if [[ "$job_status" -eq 42 ]]; then
  echo "[full-pair] slow-node preflight aborted this allocation; resubmit the same command." >&2
  exit 42
fi
test "$job_status" -eq 0

python - "$preflight_run" "$control_run" "$profile_run" "$control_binary" "$profile_binary" "$job_id" "$short_reference" "$full_reference" <<'PY'
import json
import sys
from pathlib import Path
from Local_Lab.profile_128 import elapsed_seconds, finalize_report

(
    preflight_run,
    control_run,
    profile_run,
    control_binary,
    profile_binary,
    job_id,
    short_reference,
    full_reference,
) = map(Path, sys.argv[1:])
job_id_text = str(job_id)
common = dict(nodes=4, ranks=96, tiles_i=12, tiles_j=8)
preflight = finalize_report(
    preflight_run,
    binary_source=control_binary,
    job_id=job_id_text,
    job_status=0,
    outer_steps=60,
    inner_steps=300,
    expect_profile=False,
    reference_run=short_reference,
    preserve_output_cadence=False,
    expect_diagnostics=False,
    **common,
)
profile = finalize_report(
    profile_run,
    binary_source=profile_binary,
    job_id=job_id_text,
    job_status=0,
    outer_steps=2592,
    inner_steps=12960,
    expect_profile=True,
    reference_run=full_reference,
    preserve_output_cadence=True,
    expect_diagnostics=False,
    **common,
)
control = finalize_report(
    control_run,
    binary_source=control_binary,
    job_id=job_id_text,
    job_status=0,
    outer_steps=2592,
    inner_steps=12960,
    expect_profile=False,
    reference_run=profile_run,
    preserve_output_cadence=True,
    expect_diagnostics=False,
    **common,
)
summary = {
    "schema_version": 1,
    "passed": bool(preflight["passed"] and profile["passed"] and control["passed"]),
    "job_id": job_id_text,
    "same_allocation": True,
    "nodes": 4,
    "ranks": 96,
    "ranks_per_node": 24,
    "tiles_i": 12,
    "tiles_j": 8,
    "outer_steps": 2592,
    "inner_steps": 12960,
    "preflight_run": str(preflight_run),
    "control_run": str(control_run),
    "profile_run": str(profile_run),
    "control_seconds": elapsed_seconds(control_run / "resource.log"),
    "profile_seconds": elapsed_seconds(profile_run / "resource.log"),
}
summary_path = profile_run / "full_pair_report.json"
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if not summary["passed"]:
    raise SystemExit(1)
PY

validate_official() {
  local run_dir=$1
  local official=/public/share/mcc2026_final/vali.py
  local copy=$run_dir/vali_official.py
  local diff_status

  test "$(grep -c '^dir_test = ' "$official")" -eq 1
  cp "$official" "$copy"
  sed -i "s|^dir_test = .*|dir_test = '$run_dir/output/'|" "$copy"
  set +e
  diff -u "$official" "$copy" > "$run_dir/vali_official.diff"
  diff_status=$?
  set -e
  test "$diff_status" -eq 1
  set -o pipefail
  python "$copy" 2>&1 | tee "$run_dir/vali_official.log"
  grep -Fq '最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常' "$run_dir/vali_official.log"
  echo "[full-pair] official validation PASS: $run_dir"
}

validate_official "$control_run"
validate_official "$profile_run"
echo "[full-pair] PASS"
echo "[full-pair] control_run=$control_run"
echo "[full-pair] profile_run=$profile_run"
