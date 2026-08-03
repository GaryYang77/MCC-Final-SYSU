#!/bin/bash
set -euo pipefail

command_name="${1:-validate}"
case "$command_name" in
  baseline|validate) ;;
  *) echo "usage: $0 [baseline|validate]" >&2; exit 2 ;;
esac

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"
mkdir -p Local_Lab/cluster_logs

if [[ "$command_name" == baseline && -e Local_Lab/baselines/mcc_4x20 ]]; then
  echo "refusing to overwrite existing server baseline: Local_Lab/baselines/mcc_4x20" >&2
  exit 2
fi

set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_GATE_COMMAND=${command_name}" \
  Local_Lab/cluster_gate.sbatch)
status=$?
set -e

job_id=${submission%%;*}
echo "[cluster] job_id=${job_id} exit_status=${status}"
for stream in out err; do
  log="Local_Lab/cluster_logs/mcc-demo-gate_${job_id}.${stream}"
  if [[ -f "$log" ]]; then
    echo "[cluster] ${stream}_log=${repo_root}/${log}"
    if [[ "$stream" == out ]]; then
      cat "$log"
    elif [[ -s "$log" ]]; then
      echo "[cluster] stderr tail:"
      tail -40 "$log"
    fi
  fi
done
exit "$status"
