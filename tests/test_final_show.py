"""End-to-end final podium, champion ceremony and freeze after Captain Votes."""
import json
import pytest

from test_show import auth, call, prepare, client
from test_vote_show import completed_secrets


def finalized_votes(client, headers, count, mode='target'):
    completed_secrets(client, headers, count)
    assert call(client, 'vote-mode', headers, {'mode': mode}).status_code == 200
    for team in range(1, count + 1):
        recipient = 2 if team != 2 else 1
        assert call(client, 'vote', headers, {'voter_team_id': team,
                                             'target_team_id': recipient}).status_code == 200
    published = call(client, 'publish', headers, {'action': 'votes', 'show_mode': 'cinematic'})
    assert published.status_code == 200, published.text
    for step in range(1, count + 2):
        response = call(client, 'publish', headers, {'action': 'vote-show-step', 'step': step})
        assert response.status_code == 200, response.text
    return client.get('/sochi/api/public/state').json()['state']['ranking']


@pytest.mark.parametrize('count', [10, 11])
@pytest.mark.parametrize('mode', ['target','voter'])
def test_complete_final_ceremony_private_steps_and_replay(client, count, mode):
    h = auth(client)
    # Vote show's public intermediate table carries movement-only fields.
    # FINAL freezes the canonical published ranking without those display fields.
    full = [{k:v for k,v in row.items() if k not in ('before_place','move')}
            for row in finalized_votes(client, h, count, mode)]
    full_by_team = {r['team_id']: r for r in full}
    first = full[0]
    assert call(client, 'publish', h, {'action': 'final-show-step', 'step': 1}).status_code == 409
    res=call(client, 'publish', h, {'action': 'final-show-start'})
    assert res.status_code == 200, res.text
    initial=client.get('/sochi/api/public/state').json()['state']
    assert initial['scene'] == 'final_show'
    assert initial['final_view'] == {
        'step': 0, 'max_step': 5, 'count': count,
        'revealed': [], 'current': None, 'board': [], 'champion': None,
        'tie_resolved': False, 'roster': []}
    assert initial['final_show'] == {'step':0,'max_step':5}
    assert initial['ranking'] == [] and initial['stages'] == {}
    assert 'vote_view' not in initial
    assert initial['published_votes'] == []
    assert 'podium' not in json.dumps(initial['final_show'])
    assert 'ranking' not in json.dumps(initial['final_show'])
    assert call(client, 'publish', h, {'action':'final-show-step','step':2}).status_code==409
    assert call(client, 'publish', h, {'action':'scene','scene':'final'}).status_code==409
    assert call(client, 'publish', h, {'action':'scene','scene':'winner'}).status_code==409
    assert call(client, 'publish', h, {'action':'vote-show-start'}).status_code==409
    assert call(client, 'publish', h, {'action':'votes'}).status_code==409

    announced=[]
    for step in range(1, 6):
        res=call(client,'publish',h,{'action':'final-show-step','step':step})
        assert res.status_code==200, res.text
        state=client.get('/sochi/api/public/state').json()['state']
        view=state['final_view']
        assert state['scene']=='final_show'
        assert view['step']==step and view['max_step']==5
        assert len(view['revealed'])==min(step,3)
        assert len({r['team_id'] for r in view['revealed']})==len(view['revealed'])
        assert state['final_show']=={'step':step,'max_step':5}
        assert 'podium' not in str(state['final_show'])
        assert state['published_votes']==[] and 'vote_view' not in state
        if step<=3:
            assert state['ranking']==[]
            assert view['board']==[] and view['champion'] is None
            assert view['current'] is not None
            announced.append(view['current'])
            assert view['current']['ceremony_place']==4-step
            assert view['current']['name'] == view['revealed'][-1]['name']
            assert view['current']['total']==full_by_team[view['current']['team_id']]['total']
            assert state['stages']=={}
        if step==3:
            assert announced[-1]['team_id'] == first['team_id']
        if step==4:
            assert view['current'] is None and view['champion'] is None
            assert view['board']==full
            assert state['ranking']==full
        if step==5:
            assert view['champion']['team_id'] == first['team_id']
            assert view['champion']['total'] == first['total']
            assert view['board']==full
            assert state['ranking']==full
    assert call(client,'publish',h,{'action':'final-show-step','step':6}).status_code==422
    assert call(client,'publish',h,{'action':'winner-decision','team_id':first['team_id']}).status_code==409
    assert call(client,'publish',h,{'action':'vote-show-step','step':count}).status_code==409

    # Ceremony replay never duplicates awards or changes the table.
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==200
    replay=client.get('/sochi/api/public/state').json()['state']
    assert replay['final_view']['board']==[] and replay['ranking']==[]
    assert replay['final_view']['revealed']==[]
    for step in range(1,6):
        assert call(client,'publish',h,{'action':'final-show-step','step':step}).status_code==200
    after=client.get('/sochi/api/public/state').json()['state']
    assert after['final_view']['board']==full
    assert sum(r['votes'] for r in after['ranking'])==count*10000


def test_final_blocks_before_vote_summary(client):
    h=auth(client)
    prepare(client,h,10)
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==409
    assert call(client,'publish',h,{'action':'final-show-step','step':1}).status_code==409


def test_final_tie_requires_explicit_adjudication_and_keeps_true_score(client):
    h=auth(client)
    state=prepare(client,h,10,True)
    players=[s for s in state['seats'] if s['player_id']]
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    for team_id in range(1,11):
        res=call(client,'stage',h,{
            'team_id':team_id,'green_stack':100000,'reentry_count':0,
            'blue_stack':120000,'addon_count':0,'survivors':0,'red_place':team_id})
        assert res.status_code==200,res.text
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    for phase in ('green','blue','red'):
        assert call(client,'publish',h,{'action':phase}).status_code==200
    for slot,player in enumerate(players[:3],1):
        res=call(client,'secret',h,{'slot':slot,'player_id':player['player_id'],
                                    'confirmed':False})
        assert res.status_code==200,res.text
    assert call(client,'publish',h,{'action':'secret-show-start'}).status_code==200
    for slot in range(1,4):
        assert call(client,'publish',h,{'action':'reveal','slot':slot}).status_code==200
    assert call(client,'publish',h,{'action':'secret-show-step','step':4}).status_code==200
    # GREEN 100k + BLUE 20k + RED 130k,120k => team #1 leads by 10k.
    # Votes give team #2 two ballots, team #1 one: identical 260k totals.
    recipients=[2,1,2,3,4,5,6,7,8,9]
    for voter,recipient in enumerate(recipients,1):
        assert recipient!=voter
        assert call(client,'vote',h,{'voter_team_id':voter,
                                    'target_team_id':recipient}).status_code==200
    assert call(client,'publish',h,{'action':'votes','show_mode':'cinematic'}).status_code==200
    for step in range(1,12):
        assert call(client,'publish',h,{'action':'vote-show-step','step':step}).status_code==200
    ranking=client.get('/sochi/api/public/state').json()['state']['ranking']
    assert ranking[0]['team_id']==1 and ranking[1]['team_id']==2
    assert ranking[0]['total']==ranking[1]['total']==260000
    assert ranking[0]['place']==ranking[1]['place']==1
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==409
    assert call(client,'publish',h,{'action':'winner-decision','team_id':3}).status_code==422
    assert call(client,'publish',h,{'action':'winner-decision','team_id':2}).status_code==200
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==200
    for step in range(1,6):
        assert call(client,'publish',h,{'action':'final-show-step','step':step}).status_code==200
    published=client.get('/sochi/api/public/state').json()['state']
    assert published['final_view']['champion']['team_id']==2
    assert published['final_view']['tie_resolved'] is True
    actual=published['final_view']['board']
    assert actual[0]['place']==actual[1]['place']==1
    assert actual[0]['total']==actual[1]['total']==260000
    assert call(client,'publish',h,{'action':'winner-decision','team_id':1}).status_code==409


def test_final_demo_is_only_fictional_and_read_only(client):
    before=client.get('/sochi/api/public/state').json()
    page=client.get('/sochi/preview/final')
    assert page.status_code==200
    assert 'ДЕМО ФИНАЛА · НЕ ЭФИР' in page.text
    for file in ('final-show.js','final-show.css','final-preview.js'):
        res=client.get('/sochi/static/'+file)
        assert res.status_code==200 and res.content
    assert client.get('/sochi/api/public/state').json()==before
    assert client.get('/sochi/api/admin/state').status_code==401
