"""HI JACK / HI SOCHI: final-table real-chip allotment and bonus order."""
import pytest
from test_show import auth,call,client
from test_blue_show import setup_stages
from test_blue_policy import apply_policy
from sochi_show.core import final_table_stacks,blue_points_from_policy

def start(client,h,n):
    setup_stages(client,h,n)
    state=client.get('/sochi/api/admin/state').json()
    for row in state['seats']:
        res=call(client,'player',h,{'card_id':row['card_id'],'name':'Игрок '+row['card_id']})
        assert res.status_code==200,res.text
    for tid in range(1,n+1):
        res=call(client,'stage',h,{'team_id':tid,
                 'blue_stack':900000+tid*110000,'survivors':tid%3})
        assert res.status_code==200,res.text
    assert call(client,'publish',h,{'action':'blue','show_mode':'cinematic'}).status_code==200
    for step in range(1,n+2):
        assert call(client,'publish',h,{'action':'blue-show-step','step':step}).status_code==200
    before=client.get('/sochi/api/admin/state').json()['published']
    assert 'red' not in before['published_phases']
    # RED cannot be completed yet: no captain places or approved stacks.
    assert call(client,'publish',h,{'action':'red','show_mode':'cinematic'}).status_code in (409,422)
    apply_policy(client,h,{'mode':'final_table'})
    state=client.get('/sochi/api/admin/state').json()
    policy=state['published']['blue_policy']
    assert policy['mode']=='final_table' and policy['revealed'] is False
    net={int(tid):v['blue_net_chips'] for tid,v in before['stages'].items()}
    expected=final_table_stacks(net,n)
    assert policy['points']==expected
    assert min(expected.values())==100000
    assert max(expected.values())==1000000
    public=client.get('/sochi/api/public/state').json()['state']
    assert public['blue_policy']=={'mode':'pending','revealed':False}
    assert public['ranking']==[] and public['stages']=={}
    assert all('award' not in row for row in public['blue_view']['revealed'])
    assert call(client,'publish',h,{'action':'secret-show-start'}).status_code==409
    # Old manual publishing endpoints must not bypass the new reveal order.
    assert call(client,'publish',h,{'action':'reveal','slot':1}).status_code==409
    assert call(client,'publish',h,{'action':'votes'}).status_code==409
    assert call(client,'publish',h,{'action':'blue-policy-reveal'}).status_code==200
    assert call(client,'publish',h,{'action':'votes'}).status_code==409
    public=client.get('/sochi/api/public/state').json()['state']
    assert public['blue_view']['table_mode']=='final_table'
    assert public['blue_view']['points_revealed']
    for row in public['blue_view']['revealed']:
        assert row['award']==expected[str(row['team_id'])]+row['survivor_bonus']
    return state['seats'],expected

@pytest.mark.parametrize('n',[10,11])
def test_real_final_table_before_red_with_jack_and_voting_chips(client,n):
    h=auth(client)
    seats,stacks=start(client,h,n)
    players=[r for r in seats if r['player_id']]
    killer=next(x for x in players if x['team_id']==2)
    for slot,seat in enumerate(players[:3],start=1):
        data={'slot':slot,'player_id':seat['player_id'],'confirmed':slot!=2}
        if slot!=2:
            data.update({'knockout_team_id':2,'knockout_player_id':killer['player_id']})
        assert call(client,'secret',h,data).status_code==200
    assert call(client,'publish',h,{'action':'secret-show-start'}).status_code==200
    state=client.get('/sochi/api/public/state').json()['state']
    assert state['secret_view']['jack_chips']==5000
    assert state['revealed_secrets']==[]
    assert call(client,'publish',h,{'action':'red','show_mode':'cinematic'}).status_code==409
    for slot in (1,2,3):
        assert call(client,'publish',h,{'action':'reveal','slot':slot}).status_code==200
    assert call(client,'publish',h,{'action':'secret-show-step','step':4}).status_code==200
    result=client.get('/sochi/api/admin/state').json()['published']
    assert sum(r['secret'] for r in result['ranking'])==10000
    assert next(r for r in result['ranking'] if r['team_id']==2)['secret']==10000
    for voter in range(1,n+1):
        target=2 if voter!=2 else 1
        assert call(client,'vote',h,{'voter_team_id':voter,'target_team_id':target}).status_code==200
    assert call(client,'publish',h,{'action':'votes','show_mode':'cinematic'}).status_code==200
    state=client.get('/sochi/api/public/state').json()['state']
    assert state['vote_view']['final_table'] is True
    assert state['vote_view']['revealed']==[]
    assert state['published_votes']==[]
    assert call(client,'publish',h,{'action':'red','show_mode':'cinematic'}).status_code==409
    for step in range(1,n+2):
        assert call(client,'publish',h,{'action':'vote-show-step','step':step}).status_code==200
    pub=client.get('/sochi/api/public/state').json()['state']
    assert sum(x['votes'] for x in pub['ranking'])==n*10000
    assert sum(x['secret'] for x in pub['ranking'])==10000
    for x in pub['ranking']:
        assert x['total']==stacks[str(x['team_id'])]+x['survivor_bonus']+x['secret']+x['votes']
    # RED finishing places are entered after everyone is seated and rewarded.
    for team_id in range(1,n+1):
        assert call(client,'stage',h,{'team_id':team_id,'red_place':team_id}).status_code==200
    assert call(client,'publish',h,{'action':'red','show_mode':'cinematic'}).status_code==200
    for step in range(1,n+2):
        assert call(client,'publish',h,{'action':'red-show-step','step':step}).status_code==200
    after=client.get('/sochi/api/admin/state').json()['published']
    for x in after['red_show']['ranking']:
        assert x['total']==stacks[str(x['team_id'])]+x['survivor_bonus']+x['red']+next(r for r in pub['ranking'] if r['team_id']==x['team_id'])['secret']+next(r for r in pub['ranking'] if r['team_id']==x['team_id'])['votes']
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==200
    assert client.get('/sochi/api/admin/state').json()['published']['final_show']['step']==0


def test_proportions_ties_negative_stacks_extremes():
    assert final_table_stacks({1:0,2:500,3:1000},3)=={
        '1':100000,'2':550000,'3':1000000}
    assert final_table_stacks({1:-1000,2:-500,3:0},3)=={
        '1':100000,'2':550000,'3':1000000}
    assert final_table_stacks({1:100,2:100,3:100},3)=={
        '1':550000,'2':550000,'3':550000}
    assert final_table_stacks({1:1000,2:1000,3:2000},3)=={
        '1':100000,'2':100000,'3':1000000}
    assert blue_points_from_policy({1:1,2:2,3:3},{'mode':'final_table'},3)=={
        '1':100000,'2':550000,'3':1000000}
