#!/usr/bin/env python3
"""Run full three-day PROFILE jobs sequentially at 1, 2, and 4 nodes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from .profile_128 import (
        FULL_INNER_STEPS,
        FULL_OUTER_STEPS,
        LAB_ROOT,
        RUN_ID_PATTERN,
        finalize_report,
        stage_run,
        submit,
    )
except ImportError:
    from profile_128 import (
        FULL_INNER_STEPS,
        FULL_OUTER_STEPS,
        LAB_ROOT,
        RUN_ID_PATTERN,
        finalize_report,
        stage_run,
        submit,
    )


SWEEPS_ROOT = LAB_ROOT / "runs" / "profile_scaling"


@dataclass(frozen=True)
class ScalingCase:
    name: str
    nodes: int
    ranks: int
    tiles_i: int
    tiles_j: int


SCALING_CASES = (
    ScalingCase("1node-32ranks", 1, 32, 4, 8),
    ScalingCase("2nodes-64ranks", 2, 64, 8, 8),
    ScalingCase("4nodes-128ranks", 4, 128, 8, 16),
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--label", default="full-scaling")
    parser.add_argument(
        "--time-limit",
        default="12:00:00",
        help="wall-time limit for each Slurm case (default: 12:00:00)",
    )
    return parser.parse_args()


def _sweep_id(label: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(label):
        raise ValueError("label may contain only letters, digits, dot, underscore, and dash")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{label}_{timestamp}_{os.getpid()}"


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_sweep(binary: Path, *, label: str, time_limit: str) -> tuple[bool, Path]:
    binary = binary.resolve()
    if not binary.is_file():
        raise FileNotFoundError(f"validated PROFILE binary not found: {binary}")

    sweep_dir = SWEEPS_ROOT / _sweep_id(label)
    bundle_dir = sweep_dir / "bundles"
    bundle_dir.mkdir(parents=True)
    manifest_path = sweep_dir / "sweep_report.json"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "mcc_roms_profile_scaling_sweep",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "binary": str(binary),
        "full_simulation": {
            "outer_steps": FULL_OUTER_STEPS,
            "inner_steps": FULL_INNER_STEPS,
            "preserve_official_output_cadence": True,
        },
        "comparison_scope": (
            "Each later successful case is compared with the first successful case "
            "using the existing 2 files x 13 variables contract. Full official "
            "acceptance still requires vali.py."
        ),
        "time_limit_per_case": time_limit,
        "cases": [],
        "passed": False,
    }
    _write_manifest(manifest_path, manifest)
    reference_run: Path | None = None

    print(f"[profile-scaling] sweep_dir={sweep_dir}", flush=True)
    for case in SCALING_CASES:
        print(
            f"[profile-scaling] START {case.name}: nodes={case.nodes} "
            f"ranks={case.ranks} tiles={case.tiles_i}x{case.tiles_j}",
            flush=True,
        )
        case_result: dict[str, object] = {**asdict(case), "passed": False}
        run_dir: Path | None = None
        try:
            run_dir = stage_run(
                binary,
                label=f"{label}-{case.name}",
                outer_steps=FULL_OUTER_STEPS,
                inner_steps=FULL_INNER_STEPS,
                tiles_i=case.tiles_i,
                tiles_j=case.tiles_j,
                nodes=case.nodes,
                ranks=case.ranks,
                preserve_output_cadence=True,
            )
            case_result["run_dir"] = str(run_dir)
            job_id, status = submit(
                run_dir,
                nodes=case.nodes,
                ranks=case.ranks,
                time_limit=time_limit,
                job_name=f"mcc-full-prof-{case.nodes}n",
            )
            case_result.update({"job_id": job_id, "submit_exit_status": status})
            report = finalize_report(
                run_dir,
                binary_source=binary,
                job_id=job_id,
                job_status=status,
                outer_steps=FULL_OUTER_STEPS,
                inner_steps=FULL_INNER_STEPS,
                tiles_i=case.tiles_i,
                tiles_j=case.tiles_j,
                expect_profile=True,
                reference_run=reference_run,
                nodes=case.nodes,
                ranks=case.ranks,
                preserve_output_cadence=True,
            )
            bundle_source = run_dir / "profile_bundle.json"
            bundle_copy = bundle_dir / f"{case.name}_profile_bundle.json"
            shutil.copy2(bundle_source, bundle_copy)
            case_result.update(
                {
                    "passed": bool(report["passed"]),
                    "normal_end": report["normal_end"],
                    "elapsed_wall_seconds": report["resources"][
                        "elapsed_wall_seconds"
                    ],
                    "comparison_passed": (
                        report["comparison"]["passed"]
                        if report["comparison"] is not None
                        else None
                    ),
                    "bundle": str(bundle_copy),
                }
            )
            if reference_run is None and report["passed"]:
                reference_run = run_dir
                case_result["selected_as_reference"] = True
            print(
                f"[profile-scaling] {'PASS' if report['passed'] else 'FAIL'} "
                f"{case.name}: wall={case_result['elapsed_wall_seconds']}s "
                f"bundle={bundle_copy}",
                flush=True,
            )
        except Exception as error:  # keep later node counts running overnight
            case_result["error"] = f"{type(error).__name__}: {error}"
            print(f"[profile-scaling] ERROR {case.name}: {error}", flush=True)

        manifest["cases"].append(case_result)
        _write_manifest(manifest_path, manifest)

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["passed"] = bool(
        len(manifest["cases"]) == len(SCALING_CASES)
        and all(case["passed"] for case in manifest["cases"])
    )
    _write_manifest(manifest_path, manifest)
    print(
        f"[profile-scaling] {'PASS' if manifest['passed'] else 'INCOMPLETE/FAIL'} "
        f"report={manifest_path}",
        flush=True,
    )
    return bool(manifest["passed"]), manifest_path


def main() -> int:
    arguments = _arguments()
    try:
        passed, _ = run_sweep(
            arguments.binary,
            label=arguments.label,
            time_limit=arguments.time_limit,
        )
    except (OSError, ValueError) as error:
        print(f"[profile-scaling] FATAL: {error}")
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
