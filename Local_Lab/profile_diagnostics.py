#!/usr/bin/env python3
"""Parse MCC diagnostic profile records and export bounded Perfetto traces."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = 2
META_PREFIX = "PROFILE_DIAG "
SITE_PREFIX = "PROFILE_SITE "
EVENT_PREFIX = "PROFILE_EVENT "
FIELD_PATTERN = re.compile(r"([a-z_]+)=\s*([^\s]+)")


@dataclass(frozen=True)
class SiteDefinition:
    site_id: int
    parent_region: int
    category: str
    operation: str
    phase: str
    name: str


SITE_DEFINITIONS = {
    definition.site_id: definition
    for definition in (
        SiteDefinition(101, 49, "nesting", "contact3d", "total", "contact3d_total"),
        SiteDefinition(102, 49, "nesting", "contact3d", "plan", "contact3d_plan"),
        SiteDefinition(103, 49, "nesting", "contact3d", "pack", "contact3d_pack"),
        SiteDefinition(104, 49, "nesting", "contact3d", "mpi", "contact3d_mpi"),
        SiteDefinition(105, 49, "nesting", "contact3d", "unpack", "contact3d_unpack"),
        SiteDefinition(111, 49, "nesting", "f2csum", "total", "f2csum_total"),
        SiteDefinition(112, 49, "nesting", "f2csum", "plan", "f2csum_plan"),
        SiteDefinition(113, 49, "nesting", "f2csum", "pack", "f2csum_direct_pack"),
        SiteDefinition(114, 49, "nesting", "f2csum", "mpi", "f2csum_mpi"),
        SiteDefinition(115, 49, "nesting", "f2csum", "unpack", "f2csum_unpack"),
        SiteDefinition(121, 54, "nesting", "put_refine3d", "total", "put_refine3d_total"),
        SiteDefinition(131, 35, "tracer", "corrector", "setup", "tracer_setup"),
        SiteDefinition(132, 35, "tracer", "corrector", "horizontal", "tracer_horizontal_advection"),
        SiteDefinition(133, 35, "tracer", "corrector", "vertical", "tracer_vertical_advection"),
        SiteDefinition(134, 35, "tracer", "corrector", "diffusion", "tracer_vertical_diffusion"),
        SiteDefinition(135, 35, "tracer", "corrector", "update", "tracer_final_update"),
        SiteDefinition(141, 44, "mpi", "broadcast", "real_scalar", "broadcast_real_scalar"),
        SiteDefinition(142, 44, "mpi", "broadcast", "real_1d", "broadcast_real_1d"),
        SiteDefinition(143, 44, "mpi", "broadcast", "real_2d", "broadcast_real_2d"),
        SiteDefinition(144, 44, "mpi", "broadcast", "real_3d", "broadcast_real_3d"),
        SiteDefinition(145, 44, "mpi", "broadcast", "real_4d", "broadcast_real_4d"),
        SiteDefinition(146, 44, "mpi", "broadcast", "integer", "broadcast_integer"),
        SiteDefinition(151, 40, "mpi", "halo2d", "pack", "halo2d_pack"),
        SiteDefinition(152, 40, "mpi", "halo2d", "wait", "halo2d_wait"),
        SiteDefinition(153, 40, "mpi", "halo2d", "unpack", "halo2d_unpack"),
        SiteDefinition(161, 41, "mpi", "halo3d", "pack", "halo3d_pack"),
        SiteDefinition(162, 41, "mpi", "halo3d", "wait", "halo3d_wait"),
        SiteDefinition(163, 41, "mpi", "halo3d", "unpack", "halo3d_unpack"),
        SiteDefinition(171, 42, "mpi", "halo4d", "pack", "halo4d_pack"),
        SiteDefinition(172, 42, "mpi", "halo4d", "wait", "halo4d_wait"),
        SiteDefinition(173, 42, "mpi", "halo4d", "unpack", "halo4d_unpack"),
        SiteDefinition(181, 35, "tracer", "corrector_horizontal", "setup", "horizontal_metric_mask_setup"),
        SiteDefinition(182, 35, "tracer", "corrector_horizontal", "transport", "horizontal_transport_setup"),
        SiteDefinition(183, 35, "tracer", "corrector_horizontal", "x_flux", "horizontal_x_flux"),
        SiteDefinition(184, 35, "tracer", "corrector_horizontal", "y_flux", "horizontal_y_flux"),
        SiteDefinition(185, 35, "tracer", "corrector_horizontal", "sources_nesting", "horizontal_sources_nesting"),
        SiteDefinition(186, 35, "tracer", "corrector_horizontal", "update", "horizontal_divergence_update"),
        SiteDefinition(187, 35, "tracer", "corrector_horizontal", "assembly", "horizontal_flux_assembly"),
        SiteDefinition(188, 35, "tracer", "tracer_flux_assembly", "setup", "tracer_flux_assembly_setup"),
        SiteDefinition(189, 35, "tracer", "tracer_flux_assembly", "pack", "tracer_flux_assembly_pack"),
        SiteDefinition(190, 35, "mpi", "tracer_flux_assembly", "mpi", "tracer_flux_assembly_mpi"),
        SiteDefinition(191, 35, "tracer", "tracer_flux_assembly", "unpack", "tracer_flux_assembly_unpack"),
        SiteDefinition(192, 22, "predictor", "pre_step3d", "tracer_setup", "pre_step3d_tracer_setup"),
        SiteDefinition(193, 22, "predictor", "pre_step3d", "tracer_horizontal", "pre_step3d_tracer_horizontal"),
        SiteDefinition(194, 22, "predictor", "pre_step3d", "tracer_vertical_advection", "pre_step3d_tracer_vertical_advection"),
        SiteDefinition(195, 22, "predictor", "pre_step3d", "tracer_vertical_diffusion", "pre_step3d_tracer_vertical_diffusion"),
        SiteDefinition(196, 22, "predictor", "pre_step3d", "u_momentum", "pre_step3d_u_momentum"),
        SiteDefinition(197, 22, "predictor", "pre_step3d", "v_momentum", "pre_step3d_v_momentum"),
        SiteDefinition(198, 22, "predictor", "pre_step3d", "tracer_bc_exchange", "pre_step3d_tracer_bc_exchange"),
    )
}


@dataclass(frozen=True)
class DiagnosticMeta:
    rank: int
    node: str
    local_rank: int
    mode: str
    clock_start_local: float
    clock_start_offset: float
    clock_start_rtt: float
    clock_end_local: float
    clock_end_offset: float
    clock_end_rtt: float
    events_dropped: int


@dataclass(frozen=True)
class SiteRecord:
    rank: int
    node: str
    local_rank: int
    grid: int
    model: int
    site: int
    calls: int
    wall: float
    bytes_sent: float
    bytes_recv: float
    peers_max: int


@dataclass(frozen=True)
class TraceEvent:
    rank: int
    grid: int
    model: int
    site: int
    sequence: int
    start: float
    end: float
    bytes_sent: float
    bytes_recv: float
    peers: int


def _fields(line: str, prefix: str) -> dict[str, str]:
    if not line.startswith(prefix):
        raise ValueError(f"record does not start with {prefix.strip()}: {line}")
    return dict(FIELD_PATTERN.findall(line[len(prefix) :]))


def _require(fields: dict[str, str], names: set[str], kind: str) -> None:
    missing = names - fields.keys()
    if missing:
        raise ValueError(f"{kind}: missing fields: {', '.join(sorted(missing))}")


def parse_diagnostic_lines(
    lines: Iterable[str],
) -> tuple[list[DiagnosticMeta], list[SiteRecord], list[TraceEvent]]:
    metadata: list[DiagnosticMeta] = []
    sites: list[SiteRecord] = []
    events: list[TraceEvent] = []
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            if line.startswith(META_PREFIX):
                values = _fields(line, META_PREFIX)
                names = {
                    "rank", "node", "local_rank", "mode",
                    "clock_start_local", "clock_start_offset", "clock_start_rtt",
                    "clock_end_local", "clock_end_offset", "clock_end_rtt",
                    "events_dropped",
                }
                _require(values, names, "PROFILE_DIAG")
                metadata.append(
                    DiagnosticMeta(
                        rank=int(values["rank"]), node=values["node"],
                        local_rank=int(values["local_rank"]), mode=values["mode"],
                        clock_start_local=float(values["clock_start_local"]),
                        clock_start_offset=float(values["clock_start_offset"]),
                        clock_start_rtt=float(values["clock_start_rtt"]),
                        clock_end_local=float(values["clock_end_local"]),
                        clock_end_offset=float(values["clock_end_offset"]),
                        clock_end_rtt=float(values["clock_end_rtt"]),
                        events_dropped=int(values["events_dropped"]),
                    )
                )
            elif line.startswith(SITE_PREFIX):
                values = _fields(line, SITE_PREFIX)
                names = {
                    "rank", "node", "local_rank", "grid", "model", "site",
                    "calls", "wall", "bytes_sent", "bytes_recv", "peers_max",
                }
                _require(values, names, "PROFILE_SITE")
                record = SiteRecord(
                    rank=int(values["rank"]), node=values["node"],
                    local_rank=int(values["local_rank"]), grid=int(values["grid"]),
                    model=int(values["model"]), site=int(values["site"]),
                    calls=int(values["calls"]), wall=float(values["wall"]),
                    bytes_sent=float(values["bytes_sent"]),
                    bytes_recv=float(values["bytes_recv"]),
                    peers_max=int(values["peers_max"]),
                )
                if record.site not in SITE_DEFINITIONS:
                    raise ValueError(f"unknown site ID {record.site}")
                sites.append(record)
            elif line.startswith(EVENT_PREFIX):
                values = _fields(line, EVENT_PREFIX)
                names = {
                    "rank", "grid", "model", "site", "sequence", "start", "end",
                    "bytes_sent", "bytes_recv", "peers",
                }
                _require(values, names, "PROFILE_EVENT")
                event = TraceEvent(
                    rank=int(values["rank"]), grid=int(values["grid"]),
                    model=int(values["model"]), site=int(values["site"]),
                    sequence=int(values["sequence"]), start=float(values["start"]),
                    end=float(values["end"]), bytes_sent=float(values["bytes_sent"]),
                    bytes_recv=float(values["bytes_recv"]), peers=int(values["peers"]),
                )
                if event.site not in SITE_DEFINITIONS:
                    raise ValueError(f"unknown site ID {event.site}")
                if event.end < event.start:
                    raise ValueError("trace event ends before it starts")
                events.append(event)
        except ValueError as error:
            raise ValueError(f"line {line_number}: {error}") from error
    return metadata, sites, events


def parse_diagnostic_files(
    paths: Sequence[Path],
) -> tuple[list[DiagnosticMeta], list[SiteRecord], list[TraceEvent]]:
    metadata: list[DiagnosticMeta] = []
    sites: list[SiteRecord] = []
    events: list[TraceEvent] = []
    for path in paths:
        parsed = parse_diagnostic_lines(
            path.read_text(encoding="utf-8", errors="strict").splitlines()
        )
        metadata.extend(parsed[0])
        sites.extend(parsed[1])
        events.extend(parsed[2])
    ranks = [item.rank for item in metadata]
    if len(ranks) != len(set(ranks)):
        raise ValueError("duplicate PROFILE_DIAG metadata for a rank")
    keys = [(item.rank, item.grid, item.model, item.site) for item in sites]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate PROFILE_SITE record for rank/grid/model/site")
    return metadata, sites, events


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": _percentile(values, 0.95),
        "max": max(values),
        "stdev": statistics.pstdev(values),
    }


def build_diagnostic_report(
    metadata: list[DiagnosticMeta],
    sites: list[SiteRecord],
    events: list[TraceEvent],
    *,
    source_files: Sequence[str],
) -> dict[str, object]:
    by_key: dict[tuple[int, int, int], list[SiteRecord]] = {}
    for record in sites:
        by_key.setdefault((record.grid, record.model, record.site), []).append(record)
    groups = []
    rank_metadata = {item.rank: item for item in metadata}
    for (grid, model, site), records in sorted(by_key.items()):
        definition = SITE_DEFINITIONS[site]
        record_by_rank = {record.rank: record for record in records}
        walls = [record_by_rank.get(rank).wall if rank in record_by_rank else 0.0
                 for rank in sorted(rank_metadata)]
        slow = sorted(
            (
                {
                    "rank": rank,
                    "node": rank_metadata[rank].node,
                    "wall": record_by_rank.get(rank).wall if rank in record_by_rank else 0.0,
                }
                for rank in rank_metadata
            ),
            key=lambda item: item["wall"],
            reverse=True,
        )[:5]
        total_calls = sum(record.calls for record in records)
        node_walls: dict[str, list[float]] = {}
        for rank, item in rank_metadata.items():
            node_walls.setdefault(item.node, []).append(
                record_by_rank.get(rank).wall if rank in record_by_rank else 0.0
            )
        worker_count = len(rank_metadata) or len(records)
        groups.append(
            {
                **asdict(definition),
                "grid": grid,
                "model": model,
                "ranks": worker_count,
                "active_ranks": len(records),
                "calls_total": total_calls,
                "calls_per_rank_mean": total_calls / worker_count,
                "wall": _distribution(walls),
                "wall_per_call_mean": (
                    sum(record.wall for record in records) / total_calls
                    if total_calls else None
                ),
                "bytes_sent_total": sum(record.bytes_sent for record in records),
                "bytes_recv_total": sum(record.bytes_recv for record in records),
                "peers_max": max(record.peers_max for record in records),
                "nodes": {
                    node: {**_distribution(values), "ranks": len(values)}
                    for node, values in sorted(node_walls.items())
                },
                "slow_ranks": slow,
            }
        )
    operations = []
    by_operation: dict[tuple[int, int, str], list[dict[str, object]]] = {}
    for group in groups:
        by_operation.setdefault(
            (int(group["grid"]), int(group["model"]), str(group["operation"])),
            [],
        ).append(group)
    for (grid, model, operation), operation_groups in sorted(by_operation.items()):
        total_group = next(
            (item for item in operation_groups if item["phase"] == "total"), None
        )
        phase_groups = [item for item in operation_groups if item["phase"] != "total"]
        total_mean = total_group["wall"]["mean"] if total_group else None
        phase_mean = sum(item["wall"]["mean"] for item in phase_groups)
        operations.append(
            {
                "grid": grid,
                "model": model,
                "operation": operation,
                "total_wall_mean": total_mean,
                "phase_wall_mean_sum": phase_mean,
                "phase_coverage_percent": (
                    100.0 * phase_mean / total_mean
                    if total_mean is not None and total_mean > 0.0
                    else None
                ),
                "sites": [item["site_id"] for item in operation_groups],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_files": list(source_files),
        "metadata": [asdict(item) for item in sorted(metadata, key=lambda x: x.rank)],
        "site_definitions": [
            asdict(SITE_DEFINITIONS[key]) for key in sorted(SITE_DEFINITIONS)
        ],
        "rank_records": [asdict(item) for item in sites],
        "groups": groups,
        "operations": operations,
        "trace": {
            "event_count": len(events),
            "events_dropped": sum(item.events_dropped for item in metadata),
            "ranks": sorted({item.rank for item in events}),
        },
    }


def validate_diagnostic_report(
    report: dict[str, object], *, expected_ranks: int, expected_nodes: int
) -> dict[str, object]:
    """Validate that a diagnostic artifact is complete enough for decisions."""
    failures: list[str] = []
    metadata = report.get("metadata", [])
    groups = report.get("groups", [])
    trace = report.get("trace", {})
    expected_rank_set = set(range(expected_ranks))
    actual_rank_set = {int(item["rank"]) for item in metadata}
    if actual_rank_set != expected_rank_set:
        missing = sorted(expected_rank_set - actual_rank_set)
        extra = sorted(actual_rank_set - expected_rank_set)
        failures.append(f"rank metadata mismatch: missing={missing} extra={extra}")
    nodes = {str(item["node"]) for item in metadata}
    if len(nodes) != expected_nodes:
        failures.append(f"expected {expected_nodes} nodes, found {len(nodes)}: {sorted(nodes)}")
    for item in metadata:
        if float(item["clock_end_local"]) <= float(item["clock_start_local"]):
            failures.append(f"rank {item['rank']}: invalid clock calibration span")
        if float(item["clock_start_rtt"]) < 0 or float(item["clock_end_rtt"]) < 0:
            failures.append(f"rank {item['rank']}: negative clock calibration RTT")

    active_sites = {int(group["site_id"]) for group in groups}
    required_sites = (
        set(range(101, 106))
        | set(range(111, 116))
        | {121}
        | set(range(131, 136))
        | set(range(181, 192))
        | set(range(192, 199))
    )
    missing_sites = sorted(required_sites - active_sites)
    if missing_sites:
        failures.append(f"required diagnostic sites are inactive: {missing_sites}")
    if not active_sites.intersection(range(141, 146)):
        failures.append("no real broadcast diagnostic site is active")
    for group in groups:
        if int(group["site_id"]) in required_sites and int(group["ranks"]) != expected_ranks:
            failures.append(
                f"site {group['site_id']} grid {group['grid']}: "
                f"expected {expected_ranks} rank records, found {group['ranks']}"
            )

    modes = {str(item["mode"]) for item in metadata}
    if len(modes) != 1:
        failures.append(f"inconsistent diagnostic modes: {sorted(modes)}")
    mode = next(iter(modes), "unknown")
    dropped = int(trace.get("events_dropped", 0))
    if dropped:
        failures.append(f"trace buffer dropped {dropped} events")
    if mode == "trace" and int(trace.get("event_count", 0)) <= 0:
        failures.append("trace mode produced no events")
    return {
        "passed": not failures,
        "failures": failures,
        "expected_ranks": expected_ranks,
        "expected_nodes": expected_nodes,
        "mode": mode,
    }


def validate_profile_consistency(
    diagnostics: dict[str, object], profile: dict[str, object]
) -> dict[str, object]:
    """Check diagnostic phase totals against their unchanged parent regions."""
    failures: list[str] = []
    checks: list[dict[str, object]] = []
    parents = {
        (int(item["grid"]), int(item["model"]), int(item["region"])): item
        for item in profile.get("records", [])
    }
    parent_by_operation = {
        "broadcast": 44,
        "contact3d": 49,
        "corrector": 35,
        "corrector_horizontal": 35,
        "f2csum": 49,
        "put_refine3d": 54,
        "pre_step3d": 22,
        "tracer_flux_assembly": 35,
    }
    for operation in diagnostics.get("operations", []):
        name = str(operation["operation"])
        parent_region = parent_by_operation.get(name)
        if parent_region is None:
            continue
        key = (int(operation["grid"]), int(operation["model"]), parent_region)
        parent = parents.get(key)
        if parent is None:
            continue
        parent_wall = float(parent["wall_mean"])
        measured = operation.get("total_wall_mean")
        if measured is None:
            measured = operation["phase_wall_mean_sum"]
        measured = float(measured)
        ratio = measured / parent_wall if parent_wall > 0.0 else None
        check = {
            "grid": key[0],
            "model": key[1],
            "operation": name,
            "parent_region": parent_region,
            "diagnostic_wall_mean": measured,
            "parent_wall_mean": parent_wall,
            "ratio": ratio,
        }
        checks.append(check)
        if ratio is not None and ratio > 1.10:
            failures.append(
                f"grid {key[0]} {name}: diagnostic/parent wall ratio "
                f"{ratio:.3f} exceeds 1.10"
            )
        coverage = operation.get("phase_coverage_percent")
        if name in {"contact3d", "f2csum"} and coverage is not None:
            if not 90.0 <= float(coverage) <= 110.0:
                failures.append(
                    f"grid {key[0]} {name}: child coverage {coverage:.2f}% "
                    "is outside 90-110%"
                )
    return {"passed": not failures, "failures": failures, "checks": checks}


def _correct_time(value: float, meta: DiagnosticMeta) -> float:
    span = meta.clock_end_local - meta.clock_start_local
    if span <= 0.0:
        offset = meta.clock_start_offset
    else:
        fraction = min(1.0, max(0.0, (value - meta.clock_start_local) / span))
        offset = meta.clock_start_offset + fraction * (
            meta.clock_end_offset - meta.clock_start_offset
        )
    return value - offset


def build_perfetto_trace(
    metadata: list[DiagnosticMeta], events: list[TraceEvent]
) -> dict[str, object]:
    by_rank = {item.rank: item for item in metadata}
    trace_events: list[dict[str, object]] = []
    for rank, meta in sorted(by_rank.items()):
        trace_events.append(
            {
                "ph": "M", "name": "process_name", "pid": rank, "tid": 0,
                "args": {"name": f"MPI rank {rank} ({meta.node})"},
            }
        )
    tracks = sorted({(item.rank, item.grid, item.site) for item in events})
    for rank, grid, site in tracks:
        definition = SITE_DEFINITIONS[site]
        trace_events.append(
            {
                "ph": "M",
                "name": "thread_name",
                "pid": rank,
                "tid": grid * 1000 + site,
                "args": {
                    "name": (
                        f"G{grid} R{definition.parent_region} "
                        f"{definition.name}"
                    )
                },
            }
        )
    for event in sorted(events, key=lambda item: (item.start, item.rank, item.sequence)):
        if event.rank not in by_rank:
            raise ValueError(f"trace event rank {event.rank} has no clock metadata")
        definition = SITE_DEFINITIONS[event.site]
        meta = by_rank[event.rank]
        start = _correct_time(event.start, meta)
        end = _correct_time(event.end, meta)
        trace_events.append(
            {
                "ph": "X",
                "name": definition.name,
                "cat": definition.category,
                "pid": event.rank,
                "tid": event.grid * 1000 + event.site,
                "ts": start * 1_000_000.0,
                "dur": max(0.0, end - start) * 1_000_000.0,
                "args": {
                    "grid": event.grid,
                    "model": event.model,
                    "site_id": event.site,
                    "parent_region": definition.parent_region,
                    "operation": definition.operation,
                    "phase": definition.phase,
                    "bytes_sent": event.bytes_sent,
                    "bytes_recv": event.bytes_recv,
                    "peers": event.peers,
                    "sequence": event.sequence,
                },
            }
        )
    return {
        "displayTimeUnit": "ms",
        "traceEvents": trace_events,
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "clock_alignment": "linear interpolation of measured rank-to-rank offsets",
        },
    }


def write_diagnostic_artifacts(run_dir: Path) -> tuple[Path, Path | None]:
    paths = sorted(run_dir.glob("profile_diag_rank_*.log"))
    if not paths:
        raise ValueError("no profile_diag_rank_*.log files found")
    metadata, sites, events = parse_diagnostic_files(paths)
    report = build_diagnostic_report(
        metadata, sites, events, source_files=[str(path) for path in paths]
    )
    report_path = run_dir / "profile_diagnostics.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    trace_path = None
    if events:
        trace_path = run_dir / "profile_trace.perfetto.json"
        trace_path.write_text(
            json.dumps(build_perfetto_trace(metadata, events), separators=(",", ":")),
            encoding="utf-8",
        )
    return report_path, trace_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    arguments = parser.parse_args()
    report, trace = write_diagnostic_artifacts(arguments.run_dir)
    print(report)
    if trace is not None:
        print(trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
