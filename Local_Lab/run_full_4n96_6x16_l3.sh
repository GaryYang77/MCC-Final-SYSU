#!/bin/bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

binary=${MCC_FULL_BINARY:-Local_Lab/runs/profile128/final-fastnodes-full-noprofile-4n96_20260809T095958Z_26214/oceanM}
short_reference=${MCC_SHORT_REFERENCE:-Local_Lab/runs/profile128/phase-current-paired-on_20260809T052757Z_482}
full_reference=${MCC_FULL_REFERENCE:-Local_Lab/runs/profile128/final-fastnodes-full-profile-4n96_20260809T095958Z_26214}
sha=${MCC_FULL_BINARY_SHA256:-fe0049c067b8a0efec3385c49dd9e606001d91444f7fcf176990a9f8f99f9c1e}
limit=${MCC_PREFLIGHT_MAX_SECONDS:-90}
test -x "$binary"; test -d "$short_reference"; test -d "$full_reference"
printf '%s  %s\n' "$sha" "$binary" | sha256sum -c -
source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

stage() {
  python - "$binary" "$1" "$2" "$3" "$4" <<'PY'
import sys
from pathlib import Path
from Local_Lab.profile_128 import stage_run
b,label,o,i,p=sys.argv[1:]
print(stage_run(Path(b).resolve(),label=label,outer_steps=int(o),inner_steps=int(i),
                tiles_i=6,tiles_j=16,nodes=4,ranks=96,preserve_output_cadence=p=="yes"))
PY
}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
preflight=$(stage "final-6x16-l3-preflight-${stamp}" 60 300 no)
full=$(stage "final-6x16-l3-full-noprofile-${stamp}" 2592 12960 yes)
echo "[full-6x16-l3] preflight_run=$preflight"
echo "[full-6x16-l3] full_run=$full"
set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_PREFLIGHT_RUN_DIR=${preflight},MCC_FULL_RUN_DIR=${full},MCC_PREFLIGHT_MAX_SECONDS=${limit}" \
  -o "$full/full_slurm_%j.out" -e "$full/full_slurm_%j.err" Local_Lab/full_4n96_6x16_l3.sbatch)
status=$?
set -e
job=${submission%%;*}
echo "[full-6x16-l3] job_id=$job exit_status=$status"
if [[ "$status" -eq 42 ]]; then exit 42; fi
test "$status" -eq 0

python - "$preflight" "$full" "$binary" "$job" "$short_reference" "$full_reference" <<'PY'
import json,sys
from pathlib import Path
from Local_Lab.profile_128 import elapsed_seconds,finalize_report
p,f,b,job,sref,fref=map(Path,sys.argv[1:]); common=dict(nodes=4,ranks=96,tiles_i=6,tiles_j=16)
pr=finalize_report(p,binary_source=b,job_id=str(job),job_status=0,outer_steps=60,inner_steps=300,
                   expect_profile=False,reference_run=sref,preserve_output_cadence=False,
                   expect_diagnostics=False,**common)
fr=finalize_report(f,binary_source=b,job_id=str(job),job_status=0,outer_steps=2592,inner_steps=12960,
                   expect_profile=False,reference_run=fref,preserve_output_cadence=True,
                   expect_diagnostics=False,**common)
d={"schema_version":1,"passed":bool(pr["passed"] and fr["passed"]),"job_id":str(job),
   "nodes":4,"ranks":96,"ranks_per_node":24,"tiles_i":6,"tiles_j":16,
   "binding":"l3-balanced-numa-row","outer_steps":2592,"inner_steps":12960,
   "preflight_run":str(p),"full_run":str(f),
   "preflight_seconds":elapsed_seconds(p/"resource.log"),"full_seconds":elapsed_seconds(f/"resource.log")}
(f/"full_run_report.json").write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
print(json.dumps(d,indent=2,sort_keys=True))
if not d["passed"]: raise SystemExit(1)
PY

official=/public/share/mcc2026_final/vali.py
copy=$full/vali_official.py
test "$(grep -c '^dir_test = ' "$official")" -eq 1
cp "$official" "$copy"
sed -i "s|^dir_test = .*|dir_test = '$full/output/'|" "$copy"
set +e; diff -u "$official" "$copy" > "$full/vali_official.diff"; ds=$?; set -e
test "$ds" -eq 1
set -o pipefail
python "$copy" 2>&1 | tee "$full/vali_official.log"
grep -Fq '最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常' "$full/vali_official.log"
echo "[full-6x16-l3] official validation PASS"
echo "[full-6x16-l3] full_run=$full"
