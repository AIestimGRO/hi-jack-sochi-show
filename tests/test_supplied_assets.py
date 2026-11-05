import json
from pathlib import Path
from sochi_show.core import validate_seating


def test_indexed_official_seating_and_original_logo():
    root = Path(__file__).resolve().parents[1]
    content = (root / "examples" / "hi_jack_sochi_seating_v2.json").read_text("utf8")
    data = json.loads(content)
    assert list(data["variants"]) == ["10", "11", "12", "13"]
    for n, v in data["variants"].items():
        assert len(v["cards"]) == int(n) * 3
        assert len({(c["table"], c["box"]) for c in v["cards"]}) == int(n) * 3
        assert len({c["card_id"] for c in v["cards"]}) == int(n) * 3
        teams, seats = validate_seating(data, int(n))
        assert len(teams) == int(n)
        assert len(seats) == int(n) * 3
        assert all(len({seat["table"] for seat in seats if seat["team_id"] == tid}) == 3 for tid in range(1, int(n) + 1))
    logo = (root / "sochi_show" / "static" / "hi-jack-logo.svg").read_text()
    assert logo.startswith("<svg") and "<script" not in logo
