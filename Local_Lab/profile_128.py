#!/usr/bin/env python3
"""Stage, submit, and verify a shortened 128-rank ROMS profiling run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from .profile_report import build_report, parse_profile_lines, write_csv
except ImportError:
    from profile_report import build_report, parse_profile_lines, write_csv


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPOSITORY_ROOT / "Local_Lab"
ROMS_ROOT = REPOSITORY_ROOT / "ROMS_CoSiNE15"
CANONICAL_INPUT = ROMS_ROOT / "ROMS" / "External" / "ocean_SCS_Dongsha60_bio15.in"
RUNS_ROOT = LAB_ROOT / "runs" / "profile128"
SBATCH_SCRIPT = LAB_ROOT / "profile_128.sbatch"
OUTPUT_FILES = ("SCS_avg_0001.nc", "Dongsha60_avg_0001.nc")
VARIABLES = (
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
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def render_profile_input(
    source: str,
    *,
    outer_steps: int,
    inner_steps: int,
    tiles_i: int,
    tiles_j: int,
) -> str:
    replacements = {
        "NtileI": f"{tiles_i}  {tiles_i}",
        "NtileJ": f"{tiles_j}  {tiles_j}",
        "NTIMES": f"{outer_steps}  {inner_steps}",
        "NAVG": f"{outer_steps}  {inner_steps}",
        "NDEFAVG": f"{outer_steps}  {inner_steps}",
    }
    rendered = source
    for key, value in replacements.items():
        pattern = re.compile(rf"^(\s*{re.escape(key)}\s*==)[^!\r\n]*(.*)$", re.MULTILINE)

        def replacement(match: re.Match[str]) -> str:
            comment = match.group(2).lstrip()
            return f"{match.group(1)} {value}" + (f" {comment}" if comment else "")

        rendered, count = pattern.subn(replacement, rendered)
        if count != 1:
            raise ValueError(f"expected exactly one {key} parameter, found {count}")
    return rendered


def validate_configuration(
    outer_steps: int, inner_steps: int, tiles_i: int, tiles_j: int
) -> None:
    values = (outer_steps, inner_steps, tiles_i, tiles_j)
    if any(value <= 0 for value in values):
        raise ValueError("steps and tile dimensions must be positive")
    if inner_steps != 5 * outer_steps:
        raise ValueError("nested-grid steps must preserve the 1:5 outer/inner ratio")
    if tiles_i * tiles_j != 128:
        raise ValueError(
            f"128-rank profiling requires tiles_i * tiles_j == 128, got {tiles_i * tiles_j}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_id(label: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(label):
        raise ValueError("label may contain only letters, digits, dot, underscore, and dash")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{label}_{timestamp}_{os.getpid()}"


def stage_run(
    binary: Path,
    *,
    label: str,
    outer_steps: int,
    inner_steps: int,
    tiles_i: int,
    tiles_j: int,
) -> Path:
    validate_configuration(outer_steps, inner_steps, tiles_i, tiles_j)
    if not binary.is_file():
        raise FileNotFoundError(f"validated ROMS binary not found: {binary}")
    if not (ROMS_ROOT / "Inputfiles").is_dir():
        raise FileNotFoundError("ROMS_CoSiNE15/Inputfiles is not available")

    run_dir = RUNS_ROOT / _run_id(label)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "output").mkdir()
    shutil.copy2(binary, run_dir / "oceanM")
    (run_dir / "ROMS").symlink_to(ROMS_ROOT / "ROMS", target_is_directory=True)
    (run_dir / "Inputfiles").symlink_to(
        ROMS_ROOT / "Inputfiles", target_is_directory=True
    )
    rendered = render_profile_input(
        CANONICAL_INPUT.read_text(encoding="utf-8"),
        outer_steps=outer_steps,
        inner_steps=inner_steps,
        tiles_i=tiles_i,
        tiles_j=tiles_j,
    )
    (run_dir / "ocean_profile.in").write_text(rendered, encoding="utf-8")
    return run_dir


def submit(run_dir: Path) -> tuple[str, int]:
    command = [
        "sbatch",
        "--wait",
        "--parsable",
        f"--export=ALL,MCC_PROFILE_RUN_DIR={run_dir}",
        "-o",
        str(run_dir / "slurm_%j.out"),
        "-e",
        str(run_dir / "slurm_%j.err"),
        str(SBATCH_SCRIPT),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout.strip()
    job_id = output.splitlines()[-1].split(";", 1)[0] if output else "unknown"
    return job_id, completed.returncode


def inspect_outputs(run_dir: Path) -> dict[str, object]:
    try:
        from netCDF4 import Dataset
    except ImportError as error:
        raise RuntimeError(
            "netCDF4 is required; run from the official vali conda environment"
        ) from error

    failures: list[str] = []
    shapes: dict[str, dict[str, list[int]]] = {}
    for filename in OUTPUT_FILES:
        path = run_dir / "output" / filename
        if not path.is_file():
            failures.append(f"missing output: {filename}")
            continue
        shapes[filename] = {}
        with Dataset(path) as dataset:
            for variable in VARIABLES:
                if variable not in dataset.variables:
                    failures.append(f"{filename}: missing variable {variable}")
                    continue
                values = dataset.variables[variable][:]
                payload = values.compressed() if np.ma.isMaskedArray(values) else values
                if not np.all(np.isfinite(payload)):
                    failures.append(f"{filename}: {variable} contains NaN/Inf")
                shapes[filename][variable] = list(values.shape)
    return {"passed": not failures, "failures": failures, "shapes": shapes}


def finalize_report(
    run_dir: Path,
    *,
    binary_source: Path,
    job_id: str,
    job_status: int,
    outer_steps: int,
    inner_steps: int,
    tiles_i: int,
    tiles_j: int,
    expect_profile: bool,
    reference_run: Path | None,
) -> dict[str, object]:
    model_log = run_dir / "model.log"
    normal_end = model_log.is_file() and "ROMS/TOMS: DONE" in model_log.read_text(
        encoding="utf-8", errors="replace"
    )
    output_report = inspect_outputs(run_dir)
    comparison = None
    if reference_run is not None:
        try:
            from .valid_test import compare_output_directories
        except ImportError:
            from valid_test import compare_output_directories

        result = compare_output_directories(
            reference_run / "output", run_dir / "output"
        )
        comparison = {
            "passed": result.passed,
            "failures": list(result.failures),
            "reference_run": str(reference_run),
            "metrics": {
                filename: {
                    variable: {
                        "rmse": metric.rmse,
                        "max_abs": metric.max_abs,
                        "passed": metric.passed,
                    }
                    for variable, metric in variables.items()
                }
                for filename, variables in result.metrics.items()
            },
        }
    profile_error = None
    profile_path = run_dir / "profile_report.json"
    csv_path = run_dir / "profile_records.csv"
    if expect_profile:
        try:
            profile_records = parse_profile_lines(
                model_log.read_text(encoding="utf-8", errors="replace").splitlines()
            )
            profile = build_report(profile_records, str(model_log))
            profile_path.write_text(
                json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            write_csv(profile_records, csv_path)
        except (OSError, ValueError) as error:
            profile_error = str(error)

    passed = (
        job_status == 0
        and normal_end
        and bool(output_report["passed"])
        and profile_error is None
        and (comparison is None or bool(comparison["passed"]))
    )
    report = {
        "schema_version": 1,
        "passed": passed,
        "job_id": job_id,
        "job_status": job_status,
        "normal_end": normal_end,
        "run_dir": str(run_dir),
        "binary_source": str(binary_source),
        "binary_sha256": _sha256(run_dir / "oceanM"),
        "configuration": {
            "nodes": 4,
            "ranks": 128,
            "outer_steps": outer_steps,
            "inner_steps": inner_steps,
            "tiles_i": tiles_i,
            "tiles_j": tiles_j,
        },
        "outputs": output_report,
        "comparison": comparison,
        "profile_expected": expect_profile,
        "profile_error": profile_error,
        "profile_report": str(profile_path) if profile_path.is_file() else None,
        "profile_csv": str(csv_path) if csv_path.is_file() else None,
    }
    (run_dir / "run_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--label", default="profile128")
    parser.add_argument("--outer-steps", type=int, default=12)
    parser.add_argument("--inner-steps", type=int, default=60)
    parser.add_argument("--tiles-i", type=int, default=8)
    parser.add_argument("--tiles-j", type=int, default=16)
    parser.add_argument(
        "--expect-profile",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require PROFILE_RANK records (disable for overhead control builds)",
    )
    parser.add_argument(
        "--reference-run",
        type=Path,
        help="compare the same 2x13 output contract against an earlier run",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    binary = arguments.binary.resolve()
    reference_run = arguments.reference_run.resolve() if arguments.reference_run else None
    if reference_run is not None and not reference_run.is_dir():
        raise SystemExit(f"reference run not found: {reference_run}")
    run_dir = stage_run(
        binary,
        label=arguments.label,
        outer_steps=arguments.outer_steps,
        inner_steps=arguments.inner_steps,
        tiles_i=arguments.tiles_i,
        tiles_j=arguments.tiles_j,
    )
    print(f"[profile128] run_dir={run_dir}")
    job_id, status = submit(run_dir)
    print(f"[profile128] job_id={job_id} exit_status={status}")
    report = finalize_report(
        run_dir,
        binary_source=binary,
        job_id=job_id,
        job_status=status,
        outer_steps=arguments.outer_steps,
        inner_steps=arguments.inner_steps,
        tiles_i=arguments.tiles_i,
        tiles_j=arguments.tiles_j,
        expect_profile=arguments.expect_profile,
        reference_run=reference_run,
    )
    if report["passed"]:
        print(f"[profile128] PASS: {run_dir / 'run_report.json'}")
        return 0
    print(f"[profile128] FAIL: {run_dir / 'run_report.json'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
