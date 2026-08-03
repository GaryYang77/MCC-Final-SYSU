#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"
mkdir -p Local_Lab/cluster_logs Local_Lab/builds/profiling

run_id="no_profile_$(date -u +%Y%m%dT%H%M%SZ)_$$"
build_root="$repo_root/Local_Lab/builds/profiling/$run_id"

set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_BUILD_ROOT=$build_root" \
  Local_Lab/build_no_profile.sbatch)
status=$?
set -e

job_id=${submission##*$'\n'}
job_id=${job_id%%;*}
echo "[build-no-profile] job_id=$job_id exit_status=$status"
echo "[build-no-profile] build_root=$build_root"

for stream in out err; do
  log="Local_Lab/cluster_logs/mcc-build-no-profile_${job_id}.${stream}"
  if [[ -f "$log" ]]; then
    echo "[build-no-profile] ${stream}_log=$repo_root/$log"
    if [[ "$stream" == err && -s "$log" ]]; then
      tail -40 "$log"
    fi
  fi
done

if [[ $status -eq 0 ]]; then
  test -x "$build_root/bin/oceanM"
  echo "[build-no-profile] binary=$build_root/bin/oceanM"
fi
exit "$status"
