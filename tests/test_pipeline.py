import json

from spreadtrader.backtest import Config
from spreadtrader.data import clean
from spreadtrader.run import report_markdown, write_outputs
from spreadtrader.universe import PAIRS
from tests.synthetic import universe_prices


def test_full_pipeline_writes_dashboard_files(tmp_path):
    prices, rep = clean(universe_prices())
    s = write_outputs(prices, rep, Config(), tmp_path, with_sensitivity=False)
    assert (tmp_path / "summary.json").exists()
    loaded = json.loads((tmp_path / "summary.json").read_text())
    assert len(loaded["pairs"]) == len(PAIRS)
    for p in PAIRS:
        d = json.loads((tmp_path / "pairs" / f"{p.id}.json").read_text())
        assert len(d["dates"]) == len(d["z"]) == len(d["position"])
    # the one genuinely cointegrated pair should be eligible more often than the rest
    rows = {r["id"]: r for r in loaded["pairs"]}
    good = rows[PAIRS[0].id]["windows_eligible"]
    others = [rows[p.id]["windows_eligible"] for p in PAIRS[1:]]
    assert good > max(others)
    assert "| Portfolio |" in report_markdown(s)
