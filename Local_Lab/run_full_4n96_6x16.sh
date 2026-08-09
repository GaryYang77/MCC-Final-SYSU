#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

control_binary=Local_Lab/runs/profile128/final-fastnodes-full-noprofile-4n96_20260809T095958Z_26214/oceanM
short_reference=Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482
full_reference=Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214
control_sha=fe0049c067b8a0efec3385c49dd9e606001d91444f7fcf176990a9f8f99f9c1e
preflight_limit=${MCC_PREFLIGHT_MAX_SECONDS:-90}

test -x "$control_binary"
test -d "$short_reference"
test -d "$full_reference"
printf '%s  %s\n' "$control_sha" "$control_binary" | sha256sum -c -

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

stage_run() {
  local label=$1
  local outer_steps=$2
  local inner_steps=$3
  local preserve=$4
  python - "$control_binary" "$label" "$outer_steps" "$inner_steps" "$preserve" <<'PY'
import sys
from pathlib import Path
from Local_Lab.profile_128 import stage_run

binary, label, outer_steps, inner_steps, preserve = sys.argv[1:]
run = stage_run(
    Path(binary).resolve(),
    label=label,
    outer_steps=int(outer_steps),
    inner_steps=int(inner_steps),
    tiles_i=6,
    tiles_j=16,
    nodes=4,
    ranks=96,
    preserve_output_cadence=preserve == "yes",
)
print(run)
PY
}

stamp=$(date -u +%Y%m%dT%H%M%SZ)
preflight_run=$(stage_run "final-6x16-preflight-${stamp}" 60 300 no)
full_run=$(stage_run "final-6x16-full-noprofile-${stamp}" 2592 12960 yes)

echo "[full-6x16] preflight_run=$preflight_run"
echo "[full-6x16] full_run=$full_run"

set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_PREFLIGHT_RUN_DIR=${preflight_run},MCC_FULL_RUN_DIR=${full_run},MCC_PREFLIGHT_MAX_SECONDS=${preflight_limit}" \
  -o "$full_run/full_slurm_%j.out" \
  -e "$full_run/full_slurm_%j.err" \
  Local_Lab/full_4n96_6x16.sbatch)
job_status=$?
set -e
job_id=${submission%%;*}
echo "[full-6x16] job_id=$job_id exit_status=$job_status"

if [[ "$job_status" -eq 42 ]]; then
  echo "[full-6x16] slow-node preflight aborted this allocation; resubmit the same command." >&2
  exit 42
fi
test "$job_status" -eq 0

python - "$preflight_run" "$full_run" "$control_binary" "$job_id" "$short_reference" "$full_reference" <<'PY'
import json
import sys
from pathlib import Path
from Local_Lab.profile_128 import elapsed_seconds, finalize_report

preflight_run, full_run, binary, job_id, short_reference, full_reference = map(
    Path, sys.argv[1:]
)
job_id_text = str(job_id)
common = dict(nodes=4, ranks=96, tiles_i=6, tiles_j=16)
preflight = finalize_report(
    preflight_run,
    binary_source=binary,
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
full = finalize_report(
    full_run,
    binary_source=binary,
    job_id=job_id_text,
    job_status=0,
    outer_steps=2592,
    inner_steps=12960,
    expect_profile=False,
    reference_run=full_reference,
    preserve_output_cadence=True,
    expect_diagnostics=False,
    **common,
)
summary = {
    "schema_version": 1,
    "passed": bool(preflight["passed"] and full["passed"]),
    "job_id": job_id_text,
    "nodes": 4,
    "ranks": 96,
    "ranks_per_node": 24,
    "tiles_i": 6,
    "tiles_j": 16,
    "outer_steps": 2592,
    "inner_steps": 12960,
    "preflight_run": str(preflight_run),
    "full_run": str(full_run),
    "preflight_seconds": elapsed_seconds(preflight_run / "resource.log"),
    "full_seconds": elapsed_seconds(full_run / "resource.log"),
}
summary_path = full_run / "full_run_report.json"
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if not summary["passed"]:
    raise SystemExit(1)
PY

official=/public/share/mcc2026_final/vali.py
copy=$full_run/vali_official.py
test "$(grep -c '^dir_test = ' "$official")" -eq 1
cp "$official" "$copy"
sed -i "s|^dir_test = .*|dir_test = '$full_run/output/'|" "$copy"
set +e
diff -u "$official" "$copy" > "$full_run/vali_official.diff"
diff_status=$?
set -e
test "$diff_status" -eq 1
set -o pipefail
python "$copy" 2>&1 | tee "$full_run/vali_official.log"
grep -Fq '最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常' "$full_run/vali_official.log"

echo "[full-6x16] official validation PASS"
echo "[full-6x16] full_run=$full_run"
echo "[full-6x16] report=$full_run/full_run_report.json"
