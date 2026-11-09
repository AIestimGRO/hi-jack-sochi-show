"""Approved GREEN/BLUE knockout bounty, fully eliminated teams and Wanbo broadcast."""
from io import BytesIO

from PIL import Image

from test_show import auth, call, client, prepare
from test_blue_policy import apply_policy
from sochi_show.core import final_table_stacks


def _team_player(state, team_id):
    return next(s["player_id"] for s in state["seats"]
                if s["team_id"] == team_id and s["player_id"])


def _start(client, h):
    state=prepare(client,h,10,players=True)
    assert call(client,"chips-settings",h,{"entry":50000,"reentry":30000,"addon":100000}).status_code==200
    assert call(client,"publish",h,{"action":"teams"}).status_code==200
    green=[{"team_id":i,"green_stack":300000+i*10000,"reentry_count":0}
           for i in range(1,11)]
    assert call(client,"stages/bulk",h,{"phase":"green","teams":green}).status_code==200
    assert call(client,"publish",h,{"action":"green"}).status_code==200
    return state


def _blue(client,h,eliminated=False):
    rows=[{"team_id":i,"blue_stack":700000+i*10000,
           "addon_count":0,"survivors":1} for i in range(1,11)]
    if eliminated:
        rows[0].update({"blue_stack":0,"addon_count":2,"survivors":0,
                        "blue_eliminated":1})
    result=call(client,"stages/bulk",h,{"phase":"blue","teams":rows})
    assert result.status_code==200,result.text
    result=call(client,"publish",h,{"action":"blue","show_mode":"cinematic"})
    assert result.status_code==200,result.text
    for step in range(1,12):
        result=call(client,"publish",h,{"action":"blue-show-step","step":step})
        assert result.status_code==200,result.text


def test_blue_elimination_still_deducts_addons_and_ranks_correctly(client):
    h=auth(client)
    _start(client,h)
    invalid=call(client,"stage",h,{"team_id":1,"blue_eliminated":1,
                                    "blue_stack":100,"survivors":0})
    assert invalid.status_code==422
    assert not client.get("/sochi/api/admin/state").json()["stages"]["1"]["blue_eliminated"]
    _blue(client,h,eliminated=True)
    admin=client.get("/sochi/api/admin/state").json()
    team=admin["stages"]["1"]
    assert team["blue_stack"]==0
    assert team["addon_count"]==2
    assert team["survivors"]==0
    assert team["blue_eliminated"]==1
    published=admin["published"]["stages"]["1"]
    assert published["blue_eliminated"] is True
    assert published["blue_net_chips"]==-(3*50000+2*100000)
    assert published["survivor_bonus"]==0
    net={int(key):row["blue_net_chips"]
         for key,row in admin["published"]["stages"].items()}
    stacks=final_table_stacks(net,10)
    assert stacks["1"]==100000
    apply_policy(client,h,{"mode":"final_table"})
    assert call(client,"publish",h,{"action":"blue-policy-reveal"}).status_code==200
    assert client.get("/sochi/api/admin/state").json()["published"]["blue_policy"]["points"]["1"]==100000
    assert call(client,"stage",h,{"team_id":1,"blue_eliminated":0}).status_code==409


def test_bounty_counts_frozen_once_into_red_chips_and_private_before_reveal(client):
    h=auth(client)
    seats=_start(client,h)
    p1=_team_player(seats,1)
    p2=_team_player(seats,2)
    assert call(client,"player-bounty",h,{"player_id":p1,"kind":"green","delta":2}).status_code==200
    assert call(client,"player-bounty",h,{"player_id":p1,"kind":"blue","count":3}).status_code==200
    assert call(client,"player-bounty",h,{"player_id":p2,"kind":"green","delta":1}).status_code==200
    assert call(client,"player-bounty",h,{"player_id":p2,"kind":"green","delta":-2}).status_code==422
    assert call(client,"player-bounty",h,{"player_id":p2,"kind":"blue","count":1.5}).status_code==422
    assert call(client,"player-bounty",h,{"player_id":99999,"kind":"blue","delta":1}).status_code==404
    state=client.get("/sochi/api/admin/state").json()
    assert next(s for s in state["seats"] if s["player_id"]==p1)["player_blue_bounty_count"]==3
    assert "team_bounties" not in client.get("/sochi/api/public/state").json()["state"]

    _blue(client,h)
    apply_policy(client,h,{"mode":"final_table"})
    before=client.get("/sochi/api/public/state").json()["state"]
    assert "team_bounties" not in before
    assert before["ranking"]==[]
    assert call(client,"publish",h,{"action":"blue-policy-reveal"}).status_code==200
    pub=client.get("/sochi/api/admin/state").json()["published"]
    assert pub["team_bounties"]["1"]=={"green":2,"blue":3,"chips":20000}
    assert pub["team_bounties"]["2"]=={"green":1,"blue":0,"chips":2500}
    row1=next(r for r in pub["ranking"] if r["team_id"]==1)
    assert row1["bounty_chips"]==20000
    assert row1["base_points"]==pub["blue_policy"]["points"]["1"]+row1["survivor_bonus"]+20000
    shown=next(r for r in pub["blue_show"]["ranking"] if r["team_id"]==1)
    assert shown["award"]==row1["base_points"]
    assert call(client,"player-bounty",h,{"player_id":p1,"kind":"green","delta":1}).status_code==409
    assert call(client,"publish",h,{"action":"scene","scene":"teams"}).status_code==200
    after=client.get("/sochi/api/admin/state").json()["published"]
    assert after["team_bounties"]==pub["team_bounties"]
    assert next(r for r in after["ranking"] if r["team_id"]==1)["bounty_chips"]==20000


def test_wanbo_frame_is_valid_png_and_public_only(client):
    home=client.get("/sochi/wanbo")
    assert home.status_code==200
    assert "http-equiv=\"refresh\"" in home.text
    assert "/sochi/wanbo/frame.png" in home.text
    assert "<script" not in home.text
    png=client.get("/sochi/wanbo/frame.png")
    assert png.status_code==200
    assert png.headers["content-type"]=="image/png"
    assert png.headers["cache-control"].startswith("no-store")
    assert png.content.startswith(b"\x89PNG\r\n\x1a\n")
    img=Image.open(BytesIO(png.content))
    assert img.size==(1600,900)
    h=auth(client)
    prepare(client,h,10)
    assert call(client,"publish",h,{"action":"teams"}).status_code==200
    assert call(client,"publish",h,{"action":"scene","scene":"teams"}).status_code==200
    updated=client.get("/sochi/wanbo/frame.png")
    assert updated.status_code==200
    assert updated.content!=png.content


def test_public_and_admin_pages_expose_right_versions_of_projector():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/"sochi_show/static"
    html=(root/"screen.html").read_text("utf-8")
    admin=(root/"admin.html").read_text("utf-8")
    script=(root/"admin.js").read_text("utf-8")
    assert "window.location.replace('/sochi/wanbo')" in html
    assert 'href="/sochi/wanbo"' in admin
    assert 'blue-elim-' in script
    assert 'bounty-player-summary' in script
    assert "player-bounty" in script
    assert "workflow-modules" in script
