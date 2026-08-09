#!/bin/bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"
binary=Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214/oceanM
reference=Local_Lab/runs/profile128/tile-shape-candidate-6x16-4n96_20260809T183013Z_39381
sha=d29d1fb766cc84e4db8ea0f942abda31868b03a2df4b44d864220cecb5448220
test -x "$binary"
printf '%s  %s\n' "$sha" "$binary" | sha256sum -c -
source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali
stage() {
  python - "$binary" "$1" <<'PY'
import sys
from pathlib import Path
from Local_Lab.profile_128 import stage_run
b,label=sys.argv[1:]
print(stage_run(Path(b).resolve(),label=label,outer_steps=60,inner_steps=300,
                tiles_i=6,tiles_j=16,nodes=4,ranks=96,preserve_output_cadence=False))
PY
}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
control_a=$(stage "l3-control-a-${stamp}")
candidate_a=$(stage "l3-candidate-a-${stamp}")
candidate_b=$(stage "l3-candidate-b-${stamp}")
control_b=$(stage "l3-control-b-${stamp}")
printf '[l3-abba] control_a=%s\ncandidate_a=%s\ncandidate_b=%s\ncontrol_b=%s\n' \
  "$control_a" "$candidate_a" "$candidate_b" "$control_b"
set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_CONTROL_A=${control_a},MCC_CANDIDATE_A=${candidate_a},MCC_CANDIDATE_B=${candidate_b},MCC_CONTROL_B=${control_b}" \
  -o "$candidate_a/l3_abba_slurm_%j.out" -e "$candidate_a/l3_abba_slurm_%j.err" \
  Local_Lab/4n96_6x16_l3_abba.sbatch)
status=$?
set -e
job_id=${submission%%;*}
echo "[l3-abba] job_id=$job_id exit_status=$status"
test "$status" -eq 0
python - "$control_a" "$candidate_a" "$candidate_b" "$control_b" "$binary" "$reference" "$job_id" <<'PY'
import json,sys
from pathlib import Path
from Local_Lab.profile_128 import elapsed_seconds,finalize_report
ca,aa,ab,cb=map(Path,sys.argv[1:5]); binary=Path(sys.argv[5]); reference=Path(sys.argv[6]); job=sys.argv[7]
common=dict(binary_source=binary,job_id=job,job_status=0,outer_steps=60,inner_steps=300,
            nodes=4,ranks=96,tiles_i=6,tiles_j=16,expect_profile=True,
            preserve_output_cadence=False,expect_diagnostics=False)
reports={}
for name,run,ref in (("control_a",ca,reference),("candidate_a",aa,ca),
                     ("candidate_b",ab,ca),("control_b",cb,ca)):
    reports[name]=finalize_report(run,reference_run=ref,**common)
paths=(("control_a",ca),("candidate_a",aa),("candidate_b",ab),("control_b",cb))
summary={"schema_version":1,"job_id":job,"same_allocation":True,
 "order":[n for n,_ in paths],"nodes":4,"ranks":96,"ranks_per_node":24,
 "tiles_i":6,"tiles_j":16,"passed":all(r["passed"] for r in reports.values()),
 "runs":{n:{"run_dir":str(p),"elapsed_wall_seconds":elapsed_seconds(p/"resource.log"),
            "passed":reports[n]["passed"]} for n,p in paths}}
path=aa/"l3_abba_report.json"; path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print(json.dumps(summary,indent=2,sort_keys=True))
if not summary["passed"]: raise SystemExit(1)
PY
echo "[l3-abba] PASS report=$candidate_a/l3_abba_report.json"
