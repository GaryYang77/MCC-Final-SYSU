"""Correctness gate for the MCC ROMS-CoSiNE15 optimization workflow.

Public commands (run inside Linux/WSL or a Slurm compute allocation)::

    python Local_Lab/valid_test.py baseline
    python Local_Lab/valid_test.py build
    python Local_Lab/valid_test.py validate
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any

import netCDF4
import numpy as np


VALIDATION_VARIABLES = (
    "temp",
    "salt",
    "u",
    "v",
    "zeta",
    "NO3",
    "NH4",
    "PO4",
    "diatom",
    "microzooplankton",
    "detritus",
    "oxygen",
    "TIC",
)

OUTPUT_FILES = ("SCS_avg_0001.nc", "Dongsha60_avg_0001.nc")
TOLERANCE = 1.0e-5
MIN_AVAILABLE_MEMORY_BYTES = 8 * 1024**3
COMMAND_TIMEOUT_SECONDS = 30 * 60
LOCAL_PROFILE = "local-gfortran"
CLUSTER_PROFILE = "cluster-intel"
PROFILE_ENVIRONMENT_VARIABLE = "MCC_VALIDATION_PROFILE"

LAB_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_ROOT.parent
ROMS_ROOT = REPOSITORY_ROOT / "ROMS_CoSiNE15"
CANONICAL_INPUT = ROMS_ROOT / "ROMS" / "External" / "ocean_SCS_Dongsha60_bio15.in"
BASELINE_ROOT = LAB_ROOT / "baselines" / "mcc_4x20"
BASELINES_ROOT = BASELINE_ROOT.parent
VALIDATION_RUNS_ROOT = LAB_ROOT / "runs" / "validation"
VALIDATION_BUILDS_ROOT = LAB_ROOT / "builds" / "validation"

DEMO_PARAMETERS = {
    "NtileI": "1  1",
    "NtileJ": "1  1",
    "NTIMES": "4  20",
    "NAVG": "4  20",
    "NDEFAVG": "4  20",
}


@dataclass(frozen=True)
class ValueStatistics:
    minimum: float
    mean: float
    maximum: float
    valid_count: int
    masked_count: int


@dataclass(frozen=True)
class VariableMetrics:
    rmse: float
    max_abs: float
    passed: bool
    reference: ValueStatistics
    candidate: ValueStatistics


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    metrics: dict[str, dict[str, VariableMetrics]]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class RunTiming:
    build_seconds: float
    model_wall_seconds: float
    model_cpu_seconds: float | None
    max_rss_kib: int | None


@dataclass(frozen=True)
class ModelRun:
    run_dir: Path
    output_dir: Path
    binary: Path
    input_file: Path
    timing: RunTiming


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_baseline_manifest(baseline_dir: Path, metadata: dict[str, Any]) -> Path:
    """Seal baseline outputs with hashes so accidental replacement is detected."""
    baseline_dir = Path(baseline_dir)
    output_dir = baseline_dir / "outputs_valid"
    output_metadata: dict[str, dict[str, int | str]] = {}
    for filename in OUTPUT_FILES:
        path = output_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing baseline output: {path}")
        output_metadata[filename] = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}

    manifest = {
        "schema_version": 1,
        "metadata": metadata,
        "outputs": output_metadata,
    }
    manifest_path = baseline_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def verify_baseline_integrity(baseline_dir: Path) -> tuple[str, ...]:
    """Return baseline integrity failures without modifying the baseline."""
    baseline_dir = Path(baseline_dir)
    manifest_path = baseline_dir / "manifest.json"
    if not manifest_path.is_file():
        return ("baseline manifest is missing",)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for filename in OUTPUT_FILES:
        output_path = baseline_dir / "outputs_valid" / filename
        expected = manifest.get("outputs", {}).get(filename, {}).get("sha256")
        if not output_path.is_file():
            failures.append(f"baseline output is missing: {filename}")
        elif not expected or _sha256(output_path) != expected:
            failures.append(f"baseline hash mismatch: {filename}")
    return tuple(failures)


def render_demo_input(source: str) -> str:
    """Create the fixed one-rank, 4/20-step input without touching model physics."""
    rendered = source
    for key, value in DEMO_PARAMETERS.items():
        pattern = re.compile(rf"^(\s*{re.escape(key)}\s*==)[^!\r\n]*(.*)$", re.MULTILINE)

        def replacement(match: re.Match[str]) -> str:
            comment = match.group(2).lstrip()
            suffix = f" {comment}" if comment else ""
            return f"{match.group(1)} {value}{suffix}"

        rendered, count = pattern.subn(replacement, rendered)
        if count != 1:
            raise ValueError(f"expected exactly one {key} parameter, found {count}")
    return rendered


def _run_id(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}_{os.getpid()}"


def _command_output(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def _git_arguments(*arguments: str) -> list[str]:
    return [
        "git",
        "-c",
        f"safe.directory={REPOSITORY_ROOT.as_posix()}",
        *arguments,
    ]


def _source_state() -> dict[str, str]:
    commit = _command_output(_git_arguments("rev-parse", "HEAD"))
    status = _command_output(
        _git_arguments("status", "--porcelain", "--", "ROMS_CoSiNE15")
    )
    diff = _command_output(_git_arguments("diff", "--", "ROMS_CoSiNE15"))
    return {
        "commit": commit,
        "status": status,
        "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
    }


def _validation_profile() -> str:
    profile = os.environ.get(PROFILE_ENVIRONMENT_VARIABLE, LOCAL_PROFILE)
    if profile not in (LOCAL_PROFILE, CLUSTER_PROFILE):
        raise RuntimeError(
            f"unsupported {PROFILE_ENVIRONMENT_VARIABLE}={profile!r}; "
            f"expected {LOCAL_PROFILE!r} or {CLUSTER_PROFILE!r}"
        )
    return profile


def _toolchain_metadata() -> dict[str, str]:
    profile = _validation_profile()
    compiler_name = "ifort" if profile == CLUSTER_PROFILE else "gfortran"
    return {
        "validation_profile": profile,
        "platform": platform.platform(),
        "hostname": platform.node(),
        "compiler": shutil.which(compiler_name) or compiler_name,
        "mpi_launcher": shutil.which("mpirun") or "mpirun",
        "nf_config": shutil.which("nf-config") or "nf-config",
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
    }


def _available_memory_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        raise RuntimeError("this workflow must run inside WSL/Linux")
    for line in meminfo.read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("cannot determine available memory from /proc/meminfo")


def _check_environment() -> None:
    if os.name != "posix":
        raise RuntimeError("run this workflow on Linux/WSL")
    missing = [
        path
        for path in (ROMS_ROOT, CANONICAL_INPUT, ROMS_ROOT / "Inputfiles")
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"required MCC path is missing: {missing[0]}")
    available = _available_memory_bytes()
    if available < MIN_AVAILABLE_MEMORY_BYTES:
        gib = available / 1024**3
        raise RuntimeError(
            f"refusing to run with only {gib:.2f} GiB available; "
            "at least 8 GiB is required"
        )


def _tail(path: Path, line_count: int = 40) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-line_count:])
    except FileNotFoundError:
        return "(log file was not created)"


def _run_logged(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> float:
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _terminate_process_group(process)
            raise RuntimeError(f"command timed out after {timeout}s; see {log_path}") from error
        except BaseException:
            _terminate_process_group(process)
            raise
    elapsed = time.perf_counter() - started
    if return_code != 0:
        raise RuntimeError(
            f"command failed with exit code {return_code}: {' '.join(command)}\n"
            f"last log lines:\n{_tail(log_path)}"
        )
    return elapsed


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate a build/MPI process tree when validation is interrupted."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _build_command(build_dir: Path, binary_dir: Path) -> list[str]:
    profile = _validation_profile()
    common = [
        "make",
        "-j1",
        "ROMS_APPLICATION=BYE24BIO15",
        f"SCRATCH_DIR={build_dir}",
        f"BINDIR={binary_dir}",
        "USE_MPI=on",
        "USE_NETCDF4=on",
    ]
    if profile == CLUSTER_PROFILE:
        nf_config = shutil.which("nf-config")
        if not nf_config:
            raise RuntimeError("cluster-intel profile requires nf-config from the NetCDF module")
        required = ("ifort", "mpif90", "mpirun")
        missing = [name for name in required if not shutil.which(name)]
        if missing:
            raise RuntimeError(
                "cluster-intel profile is missing loaded tools: " + ", ".join(missing)
            )
        return common + [
            "FORT=ifort",
            "USE_MPIF90=on",
            f"NF_CONFIG={nf_config}",
        ]

    return common + [
        "FORT=gfortran",
        "FC=/usr/bin/gfortran",
        "USE_MPIF90=",
        "NF_CONFIG=/usr/bin/nf-config",
        "NETCDF_INCDIR=/usr/include",
        "NETCDF_LIBDIR=/usr/lib/x86_64-linux-gnu",
        "LD=/usr/bin/gfortran",
        (
            "FFLAGS=-frepack-arrays -O2 -ffast-math "
            "-fallow-argument-mismatch -ffree-line-length-none "
            "-I/usr/include/x86_64-linux-gnu/mpich"
        ),
        "LIBS=-L/usr/lib/x86_64-linux-gnu -lnetcdff -lnetcdf -lmpichfort -lmpich",
    ]


def _build_model(run_id: str, artifact_dir: Path) -> tuple[Path, float, Path]:
    build_dir = VALIDATION_BUILDS_ROOT / run_id
    binary_dir = artifact_dir / "bin"
    build_dir.mkdir(parents=True, exist_ok=False)
    binary_dir.mkdir(parents=True, exist_ok=False)
    build_log = artifact_dir / "build.log"

    command = _build_command(build_dir, binary_dir)
    environment = os.environ.copy()
    for name in ("NETCDF", "NETCDF_INCDIR", "NETCDF_LIBDIR", "NF_CONFIG", "NC_CONFIG"):
        environment.pop(name, None)
    build_home = artifact_dir / "build_home"
    build_home.mkdir()
    environment["HOME"] = str(build_home)
    build_seconds = _run_logged(
        command,
        cwd=ROMS_ROOT,
        log_path=build_log,
        env=environment,
    )
    binary = binary_dir / "oceanM"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"build completed but executable is missing: {binary}")
    return binary, build_seconds, build_log


def build_profile_candidate() -> tuple[Path, Path]:
    """Clean-build a PROFILE candidate without running the one-rank model."""
    _check_environment()
    run_id = _run_id("candidate")
    run_dir = VALIDATION_RUNS_ROOT / run_id
    print(f"[build] clean-building current source in {run_id}...")
    binary, build_seconds, build_log = _build_model(run_id, run_dir)
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "source": _source_state(),
        "toolchain": _toolchain_metadata(),
        "build_seconds": build_seconds,
        "binary": str(binary),
        "binary_sha256": _sha256(binary),
        "build_log": str(build_log),
    }
    report_path = run_dir / "build_report.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[build] binary: {binary}")
    print(f"[build] SHA-256: {result['binary_sha256']}")
    print(f"[build] report: {report_path}")
    print("[build] PASS")
    return binary, report_path


def _localized_demo_input(output_dir_name: str) -> str:
    rendered = render_demo_input(CANONICAL_INPUT.read_text(encoding="utf-8", errors="strict"))
    roms_path = ROMS_ROOT.as_posix()
    rendered = rendered.replace("Inputfiles/", f"{roms_path}/Inputfiles/")
    rendered = rendered.replace("ROMS/", f"{roms_path}/ROMS/")
    rendered = rendered.replace("output/", f"{output_dir_name}/")
    return rendered


def _parse_resource_log(path: Path) -> tuple[float | None, int | None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    cpu_match = re.search(r"User time \(seconds\):\s*([0-9.]+)", text)
    system_match = re.search(r"System time \(seconds\):\s*([0-9.]+)", text)
    rss_match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
    cpu_seconds = None
    if cpu_match and system_match:
        cpu_seconds = float(cpu_match.group(1)) + float(system_match.group(1))
    max_rss_kib = int(rss_match.group(1)) if rss_match else None
    return cpu_seconds, max_rss_kib


def _execute_model(run_id: str, run_dir: Path, output_dir_name: str) -> ModelRun:
    _check_environment()
    run_dir.mkdir(parents=True, exist_ok=False)
    output_dir = run_dir / output_dir_name
    output_dir.mkdir()
    input_path = run_dir / "ocean_4x20.in"
    input_path.write_text(_localized_demo_input(output_dir_name), encoding="utf-8")

    binary, build_seconds, _ = _build_model(run_id, run_dir)
    model_log = run_dir / "model.log"
    resource_log = run_dir / "resource.log"
    environment = os.environ.copy()
    environment["OMP_NUM_THREADS"] = "1"
    command = [
        "/usr/bin/time",
        "-v",
        "-o",
        str(resource_log),
        "mpirun",
        "-np",
        "1",
        str(binary),
        input_path.name,
    ]
    model_wall_seconds = _run_logged(
        command,
        cwd=run_dir,
        log_path=model_log,
        env=environment,
    )
    if "ROMS/TOMS: DONE" not in model_log.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError(f"ROMS did not report successful completion; see {model_log}")
    missing_outputs = [filename for filename in OUTPUT_FILES if not (output_dir / filename).is_file()]
    if missing_outputs:
        raise RuntimeError(f"ROMS completed without expected average output: {missing_outputs}")
    model_cpu_seconds, max_rss_kib = _parse_resource_log(resource_log)
    timing = RunTiming(build_seconds, model_wall_seconds, model_cpu_seconds, max_rss_kib)
    return ModelRun(run_dir, output_dir, binary, input_path, timing)


def create_baseline() -> Path:
    """Build and run pristine source once, then seal its 4/20-step outputs."""
    if BASELINE_ROOT.exists():
        raise RuntimeError(
            f"baseline already exists and will not be overwritten: {BASELINE_ROOT}"
        )
    source_state = _source_state()
    if source_state["status"]:
        raise RuntimeError(
            "baseline creation requires an unmodified ROMS_CoSiNE15 tree; "
            f"current changes:\n{source_state['status']}"
        )

    run_id = _run_id("baseline")
    staging_dir = BASELINES_ROOT / f".{run_id}.staging"
    print("[baseline] clean source confirmed; building BYE24BIO15 with one job...")
    run = _execute_model(run_id, staging_dir, "outputs_valid")
    metadata: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": source_state,
        "application": "BYE24BIO15",
        "mpi_ranks": 1,
        "ntimes": [4, 20],
        "ntile_i": [1, 1],
        "ntile_j": [1, 1],
        "tolerance": TOLERANCE,
        "canonical_input_sha256": _sha256(CANONICAL_INPUT),
        "generated_input_sha256": _sha256(run.input_file),
        "binary_sha256": _sha256(run.binary),
        "timing": asdict(run.timing),
        "toolchain": _toolchain_metadata(),
    }
    create_baseline_manifest(staging_dir, metadata)
    staging_dir.rename(BASELINE_ROOT)
    manifest_path = BASELINE_ROOT / "manifest.json"
    print(f"[baseline] sealed outputs: {BASELINE_ROOT / 'outputs_valid'}")
    print(f"[baseline] model wall time: {run.timing.model_wall_seconds:.3f} s")
    print(f"[baseline] manifest: {manifest_path}")
    return manifest_path


def _format_validation_failures(report: ValidationReport) -> str:
    return "\n".join(f"  - {failure}" for failure in report.failures)


def validate_candidate() -> tuple[ValidationReport, Path]:
    """Clean-build current source, run 4/20 steps, compare, and write a report."""
    integrity_failures = verify_baseline_integrity(BASELINE_ROOT)
    if integrity_failures:
        raise RuntimeError("invalid baseline:\n" + "\n".join(integrity_failures))

    run_id = _run_id("candidate")
    run_dir = VALIDATION_RUNS_ROOT / run_id
    print(f"[validate] clean-building current source in {run_id}...")
    run = _execute_model(run_id, run_dir, "output")
    report = compare_output_directories(
        BASELINE_ROOT / "outputs_valid",
        run.output_dir,
        tolerance=TOLERANCE,
    )

    baseline_manifest = json.loads(
        (BASELINE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    baseline_profile = (
        baseline_manifest.get("metadata", {})
        .get("toolchain", {})
        .get("validation_profile")
    )
    current_profile = _validation_profile()
    if baseline_profile and baseline_profile != current_profile:
        raise RuntimeError(
            f"baseline profile {baseline_profile!r} does not match "
            f"current profile {current_profile!r}"
        )
    baseline_seconds = float(
        baseline_manifest["metadata"]["timing"]["model_wall_seconds"]
    )
    candidate_seconds = run.timing.model_wall_seconds
    saved_seconds = baseline_seconds - candidate_seconds
    speedup_percent = saved_seconds / baseline_seconds * 100.0
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": report.passed,
        "tolerance": TOLERANCE,
        "source": _source_state(),
        "toolchain": _toolchain_metadata(),
        "timing": {
            "baseline_model_wall_seconds": baseline_seconds,
            "candidate_model_wall_seconds": candidate_seconds,
            "saved_seconds": saved_seconds,
            "speedup_percent": speedup_percent,
            "candidate_build_seconds": run.timing.build_seconds,
            "candidate_model_cpu_seconds": run.timing.model_cpu_seconds,
            "candidate_max_rss_kib": run.timing.max_rss_kib,
        },
        "failures": list(report.failures),
        "metrics": {
            filename: {name: asdict(value) for name, value in variables.items()}
            for filename, variables in report.metrics.items()
        },
    }
    report_path = run_dir / "validation_report.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"[timing] baseline : {baseline_seconds:.3f} s")
    print(f"[timing] candidate: {candidate_seconds:.3f} s")
    print(f"[timing] saved    : {saved_seconds:+.3f} s ({speedup_percent:+.2f}%)")
    print(f"[validate] report: {report_path}")
    if report.passed:
        print(f"[validate] PASS: RMSE and max_abs are <= {TOLERANCE:.1e}")
    else:
        print("[validate] FAIL:\n" + _format_validation_failures(report))
    return report, report_path


def test_candidate_matches_baseline() -> None:
    """The fixed pytest gate used after every local source optimization."""
    report, report_path = validate_candidate()
    assert report.passed, (
        f"candidate output diverged from the sealed baseline; report: {report_path}\n"
        f"{_format_validation_failures(report)}"
    )


def _main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("baseline", "build", "validate"),
        help="create the sealed baseline, build a PROFILE candidate, or validate it",
    )
    options = parser.parse_args(arguments)
    try:
        if options.command == "baseline":
            create_baseline()
        elif options.command == "build":
            build_profile_candidate()
        else:
            report, _ = validate_candidate()
            if not report.passed:
                return 1
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


def compare_output_directories(
    reference_dir: Path,
    candidate_dir: Path,
    *,
    tolerance: float = 1.0e-5,
) -> ValidationReport:
    """Compare the two MCC average files through the public validation contract."""
    metrics: dict[str, dict[str, VariableMetrics]] = {}
    failures: list[str] = []

    for filename in OUTPUT_FILES:
        reference_path = Path(reference_dir) / filename
        candidate_path = Path(candidate_dir) / filename
        file_metrics: dict[str, VariableMetrics] = {}
        metrics[filename] = file_metrics

        if not reference_path.is_file() or not candidate_path.is_file():
            failures.append(f"missing output pair: {filename}")
            continue

        with (
            netCDF4.Dataset(reference_path, "r") as reference,
            netCDF4.Dataset(candidate_path, "r") as candidate,
        ):
            for variable_name in VALIDATION_VARIABLES:
                if variable_name not in reference.variables or variable_name not in candidate.variables:
                    failures.append(f"{filename}:{variable_name}: missing variable")
                    continue

                reference_variable = reference.variables[variable_name]
                candidate_variable = candidate.variables[variable_name]
                if reference_variable.dimensions != candidate_variable.dimensions:
                    failures.append(f"{filename}:{variable_name}: dimensions differ")
                    continue
                if reference_variable.shape != candidate_variable.shape:
                    failures.append(f"{filename}:{variable_name}: shape differs")
                    continue

                reference_data = np.ma.asarray(reference_variable[:], dtype=np.float64)
                candidate_data = np.ma.asarray(candidate_variable[:], dtype=np.float64)
                reference_mask = np.ma.getmaskarray(reference_data)
                candidate_mask = np.ma.getmaskarray(candidate_data)
                if not np.array_equal(reference_mask, candidate_mask):
                    failures.append(f"{filename}:{variable_name}: missing-value mask differs")
                    continue

                valid = ~reference_mask
                reference_values = np.asarray(reference_data.data[valid], dtype=np.float64)
                candidate_values = np.asarray(candidate_data.data[valid], dtype=np.float64)
                valid_count = int(reference_values.size)
                masked_count = int(reference_mask.size - valid_count)
                if valid_count == 0:
                    failures.append(f"{filename}:{variable_name}: no valid values")
                    continue
                if not np.all(np.isfinite(reference_values)) or not np.all(np.isfinite(candidate_values)):
                    failures.append(f"{filename}:{variable_name}: contains NaN or infinity")
                    continue

                difference = candidate_values - reference_values
                rmse = float(np.sqrt(np.mean(np.square(difference))))
                max_abs = float(np.max(np.abs(difference)))
                passed = rmse <= tolerance and max_abs <= tolerance
                reference_stats = ValueStatistics(
                    minimum=float(np.min(reference_values)),
                    mean=float(np.mean(reference_values)),
                    maximum=float(np.max(reference_values)),
                    valid_count=valid_count,
                    masked_count=masked_count,
                )
                candidate_stats = ValueStatistics(
                    minimum=float(np.min(candidate_values)),
                    mean=float(np.mean(candidate_values)),
                    maximum=float(np.max(candidate_values)),
                    valid_count=valid_count,
                    masked_count=masked_count,
                )
                file_metrics[variable_name] = VariableMetrics(
                    rmse,
                    max_abs,
                    passed,
                    reference_stats,
                    candidate_stats,
                )
                if not passed:
                    failures.append(
                        f"{filename}:{variable_name}: RMSE={rmse:.8e}, "
                        f"max_abs={max_abs:.8e}, tolerance={tolerance:.8e}"
                    )

    return ValidationReport(not failures, metrics, tuple(failures))


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
