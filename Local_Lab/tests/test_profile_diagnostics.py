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


def test_tracer_flux_assembly_subphases_are_complete_and_instrumented() -> None:
    expected = {
        188: "tracer_flux_assembly_setup",
        189: "tracer_flux_assembly_pack",
        190: "tracer_flux_assembly_mpi",
        191: "tracer_flux_assembly_unpack",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "nesting.F"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE assemble_tracer_fluxes", 1)[1].split(
        "END SUBROUTINE assemble_tracer_fluxes", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 35
        assert definition.operation == "tracer_flux_assembly"
        assert definition.name == name
        assert source.count(f"profile_site_on (profile_ng, model, {site_id})") == 1
        assert source.count(f"profile_site_off (profile_ng, model, {site_id},") == 1


def test_tracer_flux_assembly_uses_direct_contiguous_copies() -> None:
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "nesting.F"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE assemble_tracer_fluxes", 1)[1].split(
        "END SUBROUTINE assemble_tracer_fluxes", 1
    )[0]

    assert "RESHAPE(" not in source
    assert "Fpack(p)=F_west(i,k,itrc)" in source
    assert "F_west(i,k,itrc)=Fpack(p)" in source


def test_r22_pre_step3d_subphases_are_complete_and_instrumented() -> None:
    expected = {
        192: "pre_step3d_tracer_setup",
        193: "pre_step3d_tracer_horizontal",
        194: "pre_step3d_tracer_vertical_advection",
        195: "pre_step3d_tracer_vertical_diffusion",
        196: "pre_step3d_u_momentum",
        197: "pre_step3d_v_momentum",
        198: "pre_step3d_tracer_bc_exchange",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "pre_step3d.F"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE pre_step3d_tile", 1)[1].split(
        "END SUBROUTINE pre_step3d_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 22
        assert definition.operation == "pre_step3d"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r09_step2d_subphases_are_complete_and_instrumented() -> None:
    expected = {
        199: "step2d_transport_setup",
        200: "step2d_free_surface",
        201: "step2d_pressure_gradient",
        202: "step2d_advection_rotation",
        203: "step2d_viscosity",
        204: "step2d_forcing_coupling",
        205: "step2d_momentum_update",
        206: "step2d_bc_exchange",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "step2d_LF_AM3.h"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE step2d_tile", 1)[1].split(
        "END SUBROUTINE step2d_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "step2d"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1

    assert source.index("profile_site_off (ng, iNLM, 199,") < source.index(
        "IF (iif(ng).gt.nfast(ng)) RETURN"
    )


def test_r09_transport_subphases_are_complete_and_instrumented() -> None:
    expected = {
        207: "step2d_mass_flux_compute",
        208: "step2d_mass_flux_exchange",
        209: "step2d_volume_conservation",
        210: "step2d_time_average",
        211: "step2d_average_exchange",
        212: "step2d_wetdry",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "step2d_LF_AM3.h"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE step2d_tile", 1)[1].split(
        "END SUBROUTINE step2d_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "step2d_transport_detail"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r09_wetdry_subphases_are_complete_and_instrumented() -> None:
    expected = {
        213: "wetdry_rho_mask",
        214: "wetdry_current_masks",
        215: "wetdry_average_accumulate",
        216: "wetdry_average_exchange",
        217: "wetdry_final_average_masks",
        218: "wetdry_full_masks_exchange",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "wetdry.F"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE wetdry_tile", 1)[1].split(
        "END SUBROUTINE wetdry_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "wetdry"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r09_current_wetdry_masks_split_compute_and_exchange() -> None:
    expected = {
        219: "wetdry_current_masks_compute",
        220: "wetdry_current_masks_exchange",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "wetdry.F"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE wetdry_mask_tile", 1)[1].split(
        "END SUBROUTINE wetdry_mask_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "wetdry_current_masks"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r09_advection_subphases_are_complete_and_instrumented() -> None:
    expected = {
        221: "step2d_advection_flux_stencils",
        222: "step2d_advection_divergence",
        223: "step2d_coriolis",
        224: "step2d_curvilinear",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "step2d_LF_AM3.h"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE step2d_tile", 1)[1].split(
        "END SUBROUTINE step2d_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "step2d_advection"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r09_viscosity_subphases_are_complete_and_instrumented() -> None:
    expected = {
        225: "step2d_viscosity_psi_depth",
        226: "step2d_viscosity_rho_stress_flux",
        227: "step2d_viscosity_psi_stress_flux",
        228: "step2d_viscosity_divergence_update",
    }
    source = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear" / "step2d_LF_AM3.h"
    ).read_text(encoding="utf-8")
    source = source.split("SUBROUTINE step2d_tile", 1)[1].split(
        "END SUBROUTINE step2d_tile", 1
    )[0]

    for site_id, name in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        assert definition.parent_region == 9
        assert definition.operation == "step2d_viscosity"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_r19_gls_subphases_are_complete_and_instrumented() -> None:
    expected = {
        229: ("gls_predictor_horizontal", "gls_prestep.F"),
        230: ("gls_predictor_vertical", "gls_prestep.F"),
        231: ("gls_predictor_bc_exchange", "gls_prestep.F"),
        232: ("gls_corrector_setup_shear", "gls_corstep.F"),
        233: ("gls_corrector_horizontal_advection", "gls_corstep.F"),
        234: ("gls_corrector_vertical_advection", "gls_corstep.F"),
        235: ("gls_corrector_production_dissipation", "gls_corstep.F"),
        236: ("gls_corrector_implicit_solve", "gls_corstep.F"),
        237: ("gls_corrector_coefficients", "gls_corstep.F"),
        238: ("gls_corrector_bc_exchange", "gls_corstep.F"),
    }
    nonlinear = ROOT / "ROMS_CoSiNE15" / "ROMS" / "Nonlinear"

    for site_id, (name, filename) in expected.items():
        definition = SITE_DEFINITIONS[site_id]
        source = (nonlinear / filename).read_text(encoding="utf-8")
        assert definition.parent_region == 19
        assert definition.operation == "gls_vertical_mixing"
        assert definition.name == name
        assert source.count(f"profile_site_on (ng, iNLM, {site_id})") == 1
        assert source.count(f"profile_site_off (ng, iNLM, {site_id},") == 1


def test_profile_consistency_maps_gls_subphases_to_r19() -> None:
    diagnostics = {
        "operations": [
            {
                "grid": 2,
                "model": 1,
                "operation": "gls_vertical_mixing",
                "total_wall_mean": None,
                "phase_wall_mean_sum": 9.9,
                "phase_coverage_percent": None,
            }
        ]
    }
    profile = {
        "records": [
            {"grid": 2, "model": 1, "region": 19, "wall_mean": 10.0}
        ]
    }

    validation = validate_profile_consistency(diagnostics, profile)

    assert validation["passed"]
    assert validation["checks"][0]["parent_region"] == 19
    assert validation["checks"][0]["ratio"] == pytest.approx(0.99)
