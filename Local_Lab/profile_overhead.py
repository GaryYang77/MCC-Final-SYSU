#!/usr/bin/env python3
"""Measure PROFILE overhead with both binaries in one Slurm allocation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

try:
    from .profile_128 import REPOSITORY_ROOT, finalize_report, stage_run
except ImportError:
    from profile_128 import REPOSITORY_ROOT, finalize_report, stage_run


SBATCH_SCRIPT = REPOSITORY_ROOT / "Local_Lab" / "profile_overhead.sbatch"
ELAPSED_PATTERN = re.compile(
    r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(\S+)"
)


def elapsed_seconds(resource_log: Path) -> float:
    text = resource_log.read_text(encoding="utf-8", errors="replace")
    match = ELAPSED_PATTERN.search(text)
    if match is None:
        raise ValueError(f"elapsed wall time missing from {resource_log}")
    fields = match.group(1).split(":")
    if len(fields) == 2:
        minutes, seconds = fields
        return 60.0 * float(minutes) + float(seconds)
    if len(fields) == 3:
        hours, minutes, seconds = fields
        return 3600.0 * float(hours) + 60.0 * float(minutes) + float(seconds)
    raise ValueError(f"unsupported elapsed time in {resource_log}: {match.group(1)}")


def submit_pair(profile_run: Path, control_run: Path, order: str) -> tuple[str, int]:
    command = [
        "sbatch",
        "--wait",
        "--parsable",
        (
            "--export=ALL,"
            f"MCC_PROFILE_ON_RUN_DIR={profile_run},"
            f"MCC_PROFILE_OFF_RUN_DIR={control_run},"
            f"MCC_PROFILE_RUN_ORDER={order}"
        ),
        "-o",
        str(profile_run / "pair_slurm_%j.out"),
        "-e",
        str(profile_run / "pair_slurm_%j.err"),
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


def completed_job_status(job_id: str) -> tuple[bool, str]:
    completed = subprocess.run(
        ["sacct", "-X", "-n", "-j", job_id, "--format=State", "-P"],
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    states = [line.strip().split("|", 1)[0] for line in completed.stdout.splitlines()]
    states = [state for state in states if state]
    state = states[0] if states else "UNKNOWN"
    return completed.returncode == 0 and state == "COMPLETED", state


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-binary", type=Path, required=True)
    parser.add_argument("--control-binary", type=Path, required=True)
    parser.add_argument("--label", default="profile-overhead")
    parser.add_argument("--order", choices=("off-on", "on-off"), default="off-on")
    parser.add_argument("--outer-steps", type=int, default=60)
    parser.add_argument("--inner-steps", type=int, default=300)
    parser.add_argument("--tiles-i", type=int, default=8)
    parser.add_argument("--tiles-j", type=int, default=16)
    parser.add_argument("--resume-profile-run", type=Path)
    parser.add_argument("--resume-control-run", type=Path)
    parser.add_argument("--resume-job-id")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    profile_binary = arguments.profile_binary.resolve()
    control_binary = arguments.control_binary.resolve()
    common = {
        "outer_steps": arguments.outer_steps,
        "inner_steps": arguments.inner_steps,
        "tiles_i": arguments.tiles_i,
        "tiles_j": arguments.tiles_j,
    }
    resume_values = (
        arguments.resume_profile_run,
        arguments.resume_control_run,
        arguments.resume_job_id,
    )
    if any(resume_values) and not all(resume_values):
        raise SystemExit("all three --resume-* arguments must be supplied together")
    if all(resume_values):
        profile_run = arguments.resume_profile_run.resolve()
        control_run = arguments.resume_control_run.resolve()
        job_id = arguments.resume_job_id
        complete, state = completed_job_status(job_id)
        if not complete:
            raise SystemExit(f"Slurm job {job_id} is not complete: {state}")
        status = 0
        print(f"[profile-overhead] resuming completed job {job_id}")
    else:
        profile_run = stage_run(
            profile_binary, label=f"{arguments.label}-on", **common
        )
        control_run = stage_run(
            control_binary, label=f"{arguments.label}-off", **common
        )
        print(f"[profile-overhead] profile_run={profile_run}")
        print(f"[profile-overhead] control_run={control_run}")
        job_id, status = submit_pair(profile_run, control_run, arguments.order)
        print(f"[profile-overhead] job_id={job_id} exit_status={status}")

    profile_report = finalize_report(
        profile_run,
        binary_source=profile_binary,
        job_id=job_id,
        job_status=status,
        expect_profile=True,
        reference_run=None,
        **common,
    )
    control_report = finalize_report(
        control_run,
        binary_source=control_binary,
        job_id=job_id,
        job_status=status,
        expect_profile=False,
        reference_run=profile_run,
        **common,
    )
    try:
        profile_seconds = elapsed_seconds(profile_run / "resource.log")
        control_seconds = elapsed_seconds(control_run / "resource.log")
    except (OSError, ValueError) as error:
        print(f"[profile-overhead] FAIL: {error}")
        return 1

    overhead_percent = 100.0 * (profile_seconds / control_seconds - 1.0)
    report = {
        "schema_version": 1,
        "passed": bool(profile_report["passed"] and control_report["passed"]),
        "job_id": job_id,
        "order": arguments.order,
        "profile_run": str(profile_run),
        "control_run": str(control_run),
        "profile_seconds": profile_seconds,
        "control_seconds": control_seconds,
        "overhead_percent": overhead_percent,
        "same_allocation": True,
    }
    output_path = profile_run / "overhead_report.json"
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if report["passed"]:
        print(
            f"[profile-overhead] PASS: profile={profile_seconds:.2f}s "
            f"control={control_seconds:.2f}s overhead={overhead_percent:+.2f}%"
        )
        print(f"[profile-overhead] report={output_path}")
        return 0
    print(f"[profile-overhead] FAIL: {output_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
