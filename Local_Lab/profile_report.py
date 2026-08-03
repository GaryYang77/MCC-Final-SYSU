#!/usr/bin/env python3
"""Parse ROMS PROFILE_RANK records into reviewable JSON and CSV reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 1
PROFILE_PREFIX = "PROFILE_RANK "
FIELD_PATTERN = re.compile(r"([a-z_]+)=\s*([^\s]+)")
INTEGER_FIELDS = {"grid", "model", "region", "wall_max_rank"}
FLOAT_FIELDS = {
    "calls",
    "wall_min",
    "wall_mean",
    "wall_max",
    "cpu_min",
    "cpu_mean",
    "cpu_max",
    "imbalance",
}
REQUIRED_FIELDS = INTEGER_FIELDS | FLOAT_FIELDS | {"kind"}
REGION_NAMES = {
    0: "total",
    1: "allocation_and_array_initialization",
    2: "ocean_state_initialization",
    3: "input_io_read_and_distribute",
    4: "input_data_processing",
    5: "output_average_processing",
    6: "vertical_boundary_conditions",
    7: "global_information_integrals",
    8: "output_io_define_write_sync_close",
    9: "model_2d_kernel",
    12: "2d_3d_coupling_vertical_metrics",
    13: "omega_vertical_velocity",
    14: "seawater_equation_of_state",
    15: "biology_source_sink",
    19: "gls_vertical_mixing",
    21: "3d_equations_rhs",
    22: "3d_equations_predictor",
    23: "pressure_gradient",
    24: "harmonic_tracer_mixing_s_surfaces",
    25: "harmonic_tracer_mixing_geopotentials",
    30: "harmonic_stress_tensor_s_surfaces",
    31: "harmonic_stress_tensor_geopotentials",
    34: "3d_momentum_corrector",
    35: "tracer_corrector",
    39: "multiple_grid_nesting",
    40: "mpi_2d_halo_exchange",
    41: "mpi_3d_halo_exchange",
    42: "mpi_4d_halo_exchange",
    43: "mpi_lateral_boundary_exchange",
    44: "mpi_broadcast",
    45: "mpi_reduction",
    46: "mpi_data_gathering",
    47: "mpi_data_scattering",
    48: "mpi_boundary_data_gathering",
    49: "mpi_point_data_gathering",
    50: "mpi_multi_model_coupling",
}


@dataclass(frozen=True)
class ProfileRecord:
    grid: int
    model: int
    region: int
    kind: str
    calls: float
    wall_min: float
    wall_mean: float
    wall_max: float
    wall_max_rank: int
    cpu_min: float
    cpu_mean: float
    cpu_max: float
    imbalance: float


def parse_profile_lines(lines: Iterable[str]) -> list[ProfileRecord]:
    """Return all complete PROFILE_RANK records, rejecting malformed records."""
    records: list[ProfileRecord] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.startswith(PROFILE_PREFIX):
            continue
        fields = dict(FIELD_PATTERN.findall(line))
        missing = REQUIRED_FIELDS - fields.keys()
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"line {line_number}: missing PROFILE_RANK fields: {names}")
        converted: dict[str, object] = {"kind": fields["kind"]}
        try:
            converted.update({name: int(fields[name]) for name in INTEGER_FIELDS})
            converted.update({name: float(fields[name]) for name in FLOAT_FIELDS})
        except ValueError as error:
            raise ValueError(
                f"line {line_number}: invalid PROFILE_RANK numeric field"
            ) from error
        records.append(ProfileRecord(**converted))
    if not records:
        raise ValueError("no PROFILE_RANK records found")
    return records


def _group_summary(records: list[ProfileRecord], top: int) -> list[dict[str, object]]:
    groups: dict[tuple[int, int], list[ProfileRecord]] = {}
    for record in records:
        groups.setdefault((record.grid, record.model), []).append(record)

    summaries: list[dict[str, object]] = []
    for (grid, model), group in sorted(groups.items()):
        totals = [record for record in group if record.region == 0]
        if len(totals) != 1:
            raise ValueError(
                f"grid {grid} model {model}: expected one total region, found {len(totals)}"
            )
        total = totals[0]
        workers = int(round(total.calls))
        if workers <= 0:
            raise ValueError(f"grid {grid} model {model}: invalid worker count {workers}")

        categories: dict[str, dict[str, float]] = {}
        for kind in sorted({record.kind for record in group if record.region != 0}):
            inclusive_sum = sum(
                record.wall_mean
                for record in group
                if record.region != 0 and record.kind == kind
            )
            categories[kind] = {
                "inclusive_wall_mean_sum": inclusive_sum,
                "inclusive_percent_of_total": (
                    100.0 * inclusive_sum / total.wall_mean if total.wall_mean else 0.0
                ),
            }

        hotspots = []
        for record in sorted(
            (item for item in group if item.region != 0),
            key=lambda item: item.wall_mean,
            reverse=True,
        )[:top]:
            calls_per_rank = record.calls / workers
            hotspots.append(
                {
                    **asdict(record),
                    "region_name": REGION_NAMES.get(
                        record.region, f"region_{record.region}"
                    ),
                    "calls_per_rank": calls_per_rank,
                    "wall_mean_per_call": (
                        record.wall_mean / calls_per_rank if calls_per_rank else None
                    ),
                    "inclusive_percent_of_total": (
                        100.0 * record.wall_mean / total.wall_mean
                        if total.wall_mean
                        else 0.0
                    ),
                }
            )

        summaries.append(
            {
                "grid": grid,
                "model": model,
                "workers": workers,
                "total": asdict(total),
                "categories": categories,
                "hotspots": hotspots,
            }
        )
    return summaries


def build_report(
    records: list[ProfileRecord], source_log: str, top: int = 15
) -> dict[str, object]:
    cpu_timing = "enabled" if any(record.cpu_max > 0.0 for record in records) else "disabled"
    return {
        "schema_version": SCHEMA_VERSION,
        "source_log": source_log,
        "cpu_timing": cpu_timing,
        "accounting": "inclusive",
        "accounting_note": (
            "Region timers can be nested; category and hotspot percentages are "
            "inclusive and are not expected to sum to 100%."
        ),
        "groups": _group_summary(records, top),
        "records": [asdict(record) for record in records],
    }


def write_csv(records: list[ProfileRecord], path: Path) -> None:
    fieldnames = list(ProfileRecord.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_log", type=Path)
    parser.add_argument("--json", type=Path, dest="json_path")
    parser.add_argument("--csv", type=Path, dest="csv_path")
    parser.add_argument("--top", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    if arguments.top <= 0:
        raise SystemExit("--top must be positive")
    records = parse_profile_lines(
        arguments.model_log.read_text(encoding="utf-8", errors="replace").splitlines()
    )
    report = build_report(records, str(arguments.model_log), arguments.top)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.json_path:
        arguments.json_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if arguments.csv_path:
        write_csv(records, arguments.csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
