import json
from pathlib import Path

import pytest

from Local_Lab.profile_diagnostics import (
    SITE_DEFINITIONS,
    build_diagnostic_report,
    build_perfetto_trace,
    parse_diagnostic_files,
    parse_diagnostic_lines,
    validate_diagnostic_report,
    validate_profile_consistency,
    write_diagnostic_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]


SAMPLE = """\
PROFILE_DIAG rank=0 node=n0 local_rank=0 mode=trace clock_start_local=100.0 clock_start_offset=10.0 clock_start_rtt=0.001 clock_end_local=200.0 clock_end_offset=10.1 clock_end_rtt=0.002 events_dropped=0
PROFILE_SITE rank=0 node=n0 local_rank=0 grid=2 model=1 site=104 calls=2 wall=0.6 bytes_sent=1024 bytes_recv=2048 peers_max=3
PROFILE_EVENT rank=0 grid=2 model=1 site=104 sequence=1 start=120.0 end=120.2 bytes_sent=512 bytes_recv=1024 peers=3
PROFILE_DIAG rank=1 node=n1 local_rank=0 mode=trace clock_start_local=110.0 clock_start_offset=20.0 clock_start_rtt=0.003 clock_end_local=210.0 clock_end_offset=20.2 clock_end_rtt=0.004 events_dropped=1
PROFILE_SITE rank=1 node=n1 local_rank=0 grid=2 model=1 site=104 calls=2 wall=1.0 bytes_sent=1024 bytes_recv=2048 peers_max=4
PROFILE_EVENT rank=1 grid=2 model=1 site=104 sequence=1 start=130.0 end=130.4 bytes_sent=512 bytes_recv=1024 peers=4
"""


def test_summary_exposes_rank_distribution_bytes_and_slow_ranks() -> None:
    metadata, sites, events = parse_diagnostic_lines(SAMPLE.splitlines())
    report = build_diagnostic_report(metadata, sites, events, source_files=["sample"])
    group = report["groups"][0]

    assert report["schema_version"] == 2
    assert group["name"] == "contact3d_mpi"
    assert group["wall"]["median"] == pytest.approx(0.8)
    assert group["wall"]["p95"] == pytest.approx(0.98)
    assert group["bytes_sent_total"] == 2048
    assert group["slow_ranks"][0] == {"rank": 1, "node": "n1", "wall": 1.0}
    assert report["trace"]["events_dropped"] == 1


def test_perfetto_export_aligns_rank_clocks_and_preserves_arguments() -> None:
    metadata, _, events = parse_diagnostic_lines(SAMPLE.splitlines())
    trace = build_perfetto_trace(metadata, events)
    slices = [event for event in trace["traceEvents"] if event["ph"] == "X"]
    track_names = [
        event
        for event in trace["traceEvents"]
        if event["ph"] == "M" and event["name"] == "thread_name"
    ]

    assert len(slices) == 2
    assert len(track_names) == 2
    assert track_names[0]["args"]["name"] == "G2 R49 contact3d_mpi"
    assert slices[0]["name"] == "contact3d_mpi"
    assert slices[0]["args"]["bytes_recv"] == 1024
    assert slices[0]["ts"] == pytest.approx((120.0 - 10.02) * 1_000_000)
    assert slices[1]["ts"] == pytest.approx((130.0 - 20.04) * 1_000_000)


def test_duplicate_rank_metadata_and_unknown_sites_are_rejected(tmp_path: Path) -> None:
    first = tmp_path / "profile_diag_rank_00000.log"
    second = tmp_path / "profile_diag_rank_00001.log"
    meta = SAMPLE.splitlines()[0]
    first.write_text(meta + "\n", encoding="utf-8")
    second.write_text(meta + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate PROFILE_DIAG"):
        parse_diagnostic_files([first, second])

    bad = SAMPLE.replace("site=104", "site=999", 1)
    with pytest.raises(ValueError, match="unknown site ID"):
        parse_diagnostic_lines(bad.splitlines())


def test_artifact_writer_is_optional_trace_and_machine_readable(tmp_path: Path) -> None:
    path = tmp_path / "profile_diag_rank_00000.log"
    lines = [line for line in SAMPLE.splitlines() if "rank=0" in line]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_path, trace_path = write_diagnostic_artifacts(tmp_path)

    assert json.loads(report_path.read_text(encoding="utf-8"))["groups"]
    assert trace_path is not None
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert payload["displayTimeUnit"] == "ms"


def test_malformed_and_negative_duration_records_are_rejected() -> None:
    with pytest.raises(ValueError, match="missing fields"):
        parse_diagnostic_lines(["PROFILE_SITE rank=0"])
    bad = SAMPLE.replace("end=120.2", "end=119.0")
    with pytest.raises(ValueError, match="ends before"):
        parse_diagnostic_lines(bad.splitlines())


def test_parser_accepts_fortran_es_fields_with_leading_spaces() -> None:
    line = (
        "PROFILE_SITE rank=0 node=n0 local_rank=0 grid=1 model=1 "
        "site=101 calls=2 wall=  2.9376534100003937E-01 "
        "bytes_sent=  0.0000000000000000E+00 "
        "bytes_recv=  3.1731302400000000E+08 peers_max=2"
    )
    _, sites, _ = parse_diagnostic_lines([line])

    assert sites[0].wall == pytest.approx(0.29376534100003937)
    assert sites[0].bytes_recv == pytest.approx(317313024.0)


def test_validation_rejects_incomplete_rank_and_site_coverage() -> None:
    metadata, sites, events = parse_diagnostic_lines(SAMPLE.splitlines())
    report = build_diagnostic_report(metadata, sites, events, source_files=["sample"])
    validation = validate_diagnostic_report(
        report, expected_ranks=4, expected_nodes=2
    )

    assert not validation["passed"]
    assert any("rank metadata mismatch" in item for item in validation["failures"])
    assert any("required diagnostic sites" in item for item in validation["failures"])
    assert any("dropped" in item for item in validation["failures"])


def test_profile_consistency_rejects_phase_time_above_parent_region() -> None:
    diagnostics = {
        "operations": [
            {
                "grid": 2,
                "model": 1,
                "operation": "corrector",
                "total_wall_mean": None,
                "phase_wall_mean_sum": 12.0,
                "phase_coverage_percent": None,
            }
        ]
    }
    profile = {
        "records": [
            {"grid": 2, "model": 1, "region": 35, "wall_mean": 8.0}
        ]
    }

    validation = validate_profile_consistency(diagnostics, profile)

    assert not validation["passed"]
    assert validation["checks"][0]["ratio"] == pytest.approx(1.5)


def test_r35_horizontal_subphases_are_complete_and_instrumented() -> None:
    expected = {
        181: "horizontal_metric_mask_setup",
        182: "horizontal_transport_setup",
        183: "horizontal_x_flux",
        184: "horizontal_y_flux",
        185: "horizontal_sources_nesting",
        186: "horizontal_divergence_update",
        187: "horizontal_flux_assembly",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "step3d_t.F"
    ).read_text(encoding="utf-8")

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 35
        assert definition.operation == "corrector_horizontal"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_profile_consistency_maps_horizontal_subphases_to_r35() -> None:
    diagnostics = {
        "operations": [
            {
                "grid": 2,
                "model": 1,
                "operation": "corrector_horizontal",
                "total_wall_mean": None,
                "phase_wall_mean_sum": 7.0,
                "phase_coverage_percent": None,
            }
        ]
    }
    profile = {
        "records": [
            {"grid": 2, "model": 1, "region": 35, "wall_mean": 10.0}
        ]
    }

    validation = validate_profile_consistency(diagnostics, profile)

    assert validation["passed"]
    assert validation["checks"][0]["ratio"] == pytest.approx(0.7)
