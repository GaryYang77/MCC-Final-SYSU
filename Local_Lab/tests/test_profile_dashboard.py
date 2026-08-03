from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "Local_Lab" / "profile_dashboard.html"


def test_dashboard_is_offline_and_accepts_one_json_bundle() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="fileInput" type="file"' in source
    assert "mcc_roms_profile_bundle" in source
    assert "profile_bundle.json" in source
    assert "<script src=" not in source
    assert "https://" not in source


def test_dashboard_surfaces_hotspots_rank_ranges_and_physical_value_ranges() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")

    for identifier in (
        'id="gridPanels"',
        'id="nestingPanels"',
        'id="imbalancePanels"',
        'id="variableTable"',
        'id="recordTable"',
    ):
        assert identifier in source
    assert "ref.minimum" in source
    assert "ref.mean" in source
    assert "ref.maximum" in source
    assert "candidate.minimum" in source
    assert "candidate.mean" in source
    assert "candidate.maximum" in source
    assert "RMSE" in source
    assert "Max abs" in source
    assert "inclusive" in source
