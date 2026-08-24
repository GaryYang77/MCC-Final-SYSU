#!/usr/bin/env python3
"""Report structural and numerical differences between NetCDF output sets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import netCDF4
import numpy as np


SCHEMA_VERSION = 1


class ComparisonError(RuntimeError):
    """Raised when a requested comparison cannot be performed."""


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise argparse.ArgumentTypeError("file names must be relative paths without '..'")
    return path


def _is_numeric(variable: netCDF4.Variable) -> bool:
    return np.issubdtype(np.dtype(variable.dtype), np.number)


def _statistics(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    return {
        "count": int(values.size),
        "finite_count": int(finite.size),
        "nan_count": int(np.count_nonzero(np.isnan(values))),
        "infinite_count": int(np.count_nonzero(np.isinf(values))),
        "minimum": float(np.min(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "maximum": float(np.max(finite)) if finite.size else None,
    }


def _variable_names(
    reference: netCDF4.Dataset,
    requested: Iterable[str] | None,
) -> list[str]:
    if requested:
        return list(dict.fromkeys(requested))
    return [
        name
        for name, variable in reference.variables.items()
        if _is_numeric(variable)
    ]


def _compare_variable(
    reference: netCDF4.Dataset,
    candidate: netCDF4.Dataset,
    name: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "issues": [],
        "exact_equal": False,
        "rmse": None,
        "max_abs": None,
        "reference": None,
        "candidate": None,
    }
    issues: list[str] = result["issues"]

    if name not in reference.variables:
        issues.append("missing from reference")
        return result
    if name not in candidate.variables:
        issues.append("missing from candidate")
        return result

    reference_variable = reference.variables[name]
    candidate_variable = candidate.variables[name]
    result["reference_dimensions"] = list(reference_variable.dimensions)
    result["candidate_dimensions"] = list(candidate_variable.dimensions)
    result["reference_shape"] = list(reference_variable.shape)
    result["candidate_shape"] = list(candidate_variable.shape)
    result["reference_dtype"] = str(reference_variable.dtype)
    result["candidate_dtype"] = str(candidate_variable.dtype)

    if not _is_numeric(reference_variable) or not _is_numeric(candidate_variable):
        issues.append("variable is not numeric in both files")
        return result
    if reference_variable.dimensions != candidate_variable.dimensions:
        issues.append("dimensions differ")
    if reference_variable.shape != candidate_variable.shape:
        issues.append("shape differs")
    if np.dtype(reference_variable.dtype) != np.dtype(candidate_variable.dtype):
        issues.append("dtype differs")
    if reference_variable.shape != candidate_variable.shape:
        return result

    reference_data = np.ma.asarray(reference_variable[:])
    candidate_data = np.ma.asarray(candidate_variable[:])
    reference_mask = np.ma.getmaskarray(reference_data)
    candidate_mask = np.ma.getmaskarray(candidate_data)
    mask_equal = bool(np.array_equal(reference_mask, candidate_mask))
    result["mask_equal"] = mask_equal
    result["reference_masked_count"] = int(np.count_nonzero(reference_mask))
    result["candidate_masked_count"] = int(np.count_nonzero(candidate_mask))
    if not mask_equal:
        issues.append("missing-value mask differs")

    reference_raw_values = np.ascontiguousarray(reference_data.data[~reference_mask])
    candidate_raw_values = np.ascontiguousarray(candidate_data.data[~candidate_mask])
    reference_values = np.asarray(reference_raw_values, dtype=np.float64)
    candidate_values = np.asarray(candidate_raw_values, dtype=np.float64)
    result["reference"] = _statistics(reference_values)
    result["candidate"] = _statistics(candidate_values)

    reference_finite = bool(np.all(np.isfinite(reference_values)))
    candidate_finite = bool(np.all(np.isfinite(candidate_values)))
    if not reference_finite:
        issues.append("reference contains NaN or infinity")
    if not candidate_finite:
        issues.append("candidate contains NaN or infinity")

    if not mask_equal or not reference_finite or not candidate_finite:
        return result

    difference = candidate_values - reference_values
    result["rmse"] = float(np.sqrt(np.mean(np.square(difference)))) if difference.size else 0.0
    result["max_abs"] = float(np.max(np.abs(difference))) if difference.size else 0.0
    result["exact_equal"] = bool(
        not issues
        and reference_raw_values.tobytes() == candidate_raw_values.tobytes()
    )
    return result


def compare_directories(
    reference_dir: Path,
    candidate_dir: Path,
    files: Iterable[Path],
    variables: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Compare requested file pairs and return a JSON-serializable report."""
    reference_dir = Path(reference_dir)
    candidate_dir = Path(candidate_dir)
    file_reports: dict[str, Any] = {}
    compared = 0
    exact = 0
    issues = 0

    for relative_path in files:
        reference_path = reference_dir / relative_path
        candidate_path = candidate_dir / relative_path
        if not reference_path.is_file():
            raise ComparisonError(f"reference file does not exist: {reference_path}")
        if not candidate_path.is_file():
            raise ComparisonError(f"candidate file does not exist: {candidate_path}")

        try:
            with (
                netCDF4.Dataset(reference_path, "r") as reference,
                netCDF4.Dataset(candidate_path, "r") as candidate,
            ):
                names = _variable_names(reference, variables)
                variable_reports = {
                    name: _compare_variable(reference, candidate, name) for name in names
                }
        except (OSError, RuntimeError, ValueError) as error:
            raise ComparisonError(f"cannot read NetCDF pair {relative_path}: {error}") from error

        file_reports[str(relative_path)] = {"variables": variable_reports}
        for result in variable_reports.values():
            compared += 1
            exact += int(result["exact_equal"])
            issues += len(result["issues"])

    return {
        "schema_version": SCHEMA_VERSION,
        "reference_dir": str(reference_dir.resolve()),
        "candidate_dir": str(candidate_dir.resolve()),
        "files": file_reports,
        "summary": {
            "files": len(file_reports),
            "variables": compared,
            "exact_equal_variables": exact,
            "variables_with_differences": compared - exact,
            "structural_or_data_issues": issues,
        },
    }


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.8e}"


def print_summary(report: dict[str, Any]) -> None:
    """Print a compact metric summary without assigning PASS/FAIL."""
    for filename, file_report in report["files"].items():
        for name, result in file_report["variables"].items():
            issue_text = "; ".join(result["issues"]) if result["issues"] else "none"
            print(
                f"{filename}:{name} "
                f"exact_equal={str(result['exact_equal']).lower()} "
                f"rmse={_format_metric(result['rmse'])} "
                f"max_abs={_format_metric(result['max_abs'])} "
                f"issues={issue_text}"
            )
    summary = report["summary"]
    print(
        "summary: "
        f"files={summary['files']} variables={summary['variables']} "
        f"exact_equal={summary['exact_equal_variables']} "
        f"different={summary['variables_with_differences']} "
        f"issues={summary['structural_or_data_issues']}"
    )


def _arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument(
        "--file",
        action="append",
        type=_safe_relative_path,
        required=True,
        dest="files",
        help="relative NetCDF file path; repeat to compare multiple files",
    )
    parser.add_argument(
        "--variable",
        action="append",
        dest="variables",
        help="variable name; repeat to select a subset (default: all numeric reference variables)",
    )
    parser.add_argument("--json", type=Path, dest="json_path", help="write the full report as JSON")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        report = compare_directories(
            options.reference_dir,
            options.candidate_dir,
            options.files,
            options.variables,
        )
        if options.json_path:
            options.json_path.parent.mkdir(parents=True, exist_ok=True)
            options.json_path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (ComparisonError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
