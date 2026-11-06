"""CAPTAINS projection: published-only roster and completely fictional rehearsal."""
import pytest

from test_show import auth, call, prepare, client


@pytest.mark.parametrize('count', [10, 11])
def test_captains_remains_published_roster_and_respects_selected_captains(client, count):
    h=auth(client)
    draft=prepare(client,h,count,True)
    seats=draft['seats']
    leaders={}
    for seat in seats:
        leaders.setdefault(seat['team_id'],seat)
    assert len(leaders)==count
    for id in (1,4):
        result=call(client,'team',h,{'team_id':id,'captain_player_id':leaders[id]['player_id']})
        assert result.status_code==200,result.text
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    before=client.get('/sochi/api/public/state').json()['state']
    assert before['captains']==[]
    response=call(client,'publish',h,{'action':'captains'})
    assert response.status_code==200,response.text
    pub=client.get('/sochi/api/public/state').json()['state']
    assert pub['scene']=='captains'
    assert pub['team_count']==count
    assert len(pub['captains'])==count
    assert [c['team_id'] for c in pub['captains']]==list(range(1,count+1))
    assigned={c['team_id']:c for c in pub['captains'] if c['player_id'] is not None}
    assert set(assigned)=={1,4}
    for id in (1,4):
        assert assigned[id]['player_id']==leaders[id]['player_id']
        assert assigned[id]['name']==leaders[id]['player_name']
    assert len([c for c in pub['captains'] if c['player_id'] is None])==count-2
    # Draft changes cannot affect the already published captain portrait/name.
    assert call(client,'team',h,{'team_id':1,'captain_player_id':None}).status_code==200
    unchanged=client.get('/sochi/api/public/state').json()['state']
    assert unchanged['captains']==pub['captains']


def test_captain_demo_is_fictional_and_never_mutates_tournament(client):
    before=client.get('/sochi/api/public/state').json()
    page=client.get('/sochi/preview/captains')
    assert page.status_code==200
    assert 'ДЕМО КАПИТАНОВ · НЕ ЭФИР' in page.text
    for asset in ('captain-show.js','captain-show.css','captain-preview.js'):
        res=client.get('/sochi/static/'+asset)
        assert res.status_code==200 and res.content
    show=client.get('/sochi/screen')
    assert show.status_code==200
    assert 'captain-show.js?v=captains-v1' in show.text
    assert client.get('/sochi/api/public/state').json()==before
    assert client.get('/sochi/api/admin/state').status_code==401
