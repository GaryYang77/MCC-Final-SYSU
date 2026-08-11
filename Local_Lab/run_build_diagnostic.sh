#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"
mkdir -p Local_Lab/cluster_logs Local_Lab/builds/profiling

run_id="diagnostic_$(date -u +%Y%m%dT%H%M%SZ)_$$"
build_root="$repo_root/Local_Lab/builds/profiling/$run_id"
diagnostic_sources=(
  ROMS_CoSiNE15/ROMS/Modules/mod_parallel.F
  ROMS_CoSiNE15/ROMS/Utility/timers.F
  ROMS_CoSiNE15/ROMS/Utility/distribute.F
  ROMS_CoSiNE15/ROMS/Nonlinear/nesting.F
  ROMS_CoSiNE15/ROMS/Nonlinear/step3d_t.F
  ROMS_CoSiNE15/ROMS/Nonlinear/gls_prestep.F
  ROMS_CoSiNE15/ROMS/Nonlinear/gls_corstep.F
  ROMS_CoSiNE15/ROMS/Nonlinear/Biology/bio_UMAINE15.h
)
diagnostic_source_sha256=$(
  sha256sum "${diagnostic_sources[@]}" | sha256sum | awk '{print $1}'
)

set +e
submission=$(sbatch --wait --parsable \
  --export="ALL,MCC_BUILD_ROOT=$build_root,MCC_DIAGNOSTIC_SOURCE_SHA256=$diagnostic_source_sha256" \
  Local_Lab/build_diagnostic.sbatch)
status=$?
set -e

job_id=${submission##*$'\n'}
job_id=${job_id%%;*}
echo "[build-diagnostic] job_id=$job_id exit_status=$status"
echo "[build-diagnostic] build_root=$build_root"
echo "[build-diagnostic] source_sha256=$diagnostic_source_sha256"

for stream in out err; do
  log="Local_Lab/cluster_logs/mcc-build-diagnostic_${job_id}.${stream}"
  if [[ -f "$log" ]]; then
    echo "[build-diagnostic] ${stream}_log=$repo_root/$log"
    if [[ "$stream" == err && -s "$log" ]]; then
      tail -40 "$log"
    fi
  fi
done

if [[ $status -eq 0 ]]; then
  test -x "$build_root/bin/oceanM"
  sha256sum "$build_root/bin/oceanM"
  echo "[build-diagnostic] binary=$build_root/bin/oceanM"
fi
exit "$status"
