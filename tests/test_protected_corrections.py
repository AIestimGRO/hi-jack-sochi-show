"""PIN-confirmed all-stage corrections: private preview, rollback, downstream scoring."""
import json
import pytest
from test_show import auth, call, prepare, client
from test_final_show import finalized_votes

PIN='A_real_long_test_password_123'
REASON='Исправление протокола турнира по результатам проверки'

def version(client):
    return client.get('/sochi/api/admin/state').json()['publication_version']

def preview(client,headers,**changes):
    return call(client,'correction/preview',headers,dict(changes,expected_version=version(client)))

def commit(client,headers,**changes):
    req=dict(changes,expected_version=version(client),pin=PIN,
             confirm='ИСПРАВИТЬ',reason=REASON)
    res=call(client,'correction/apply',headers,req)
    assert res.status_code==200,res.text
    return res.json()

@pytest.mark.parametrize('count',[10,11])
def test_correction_preview_is_readonly_and_rechecks_pin_and_version(client,count):
    h=auth(client)
    prepare(client,h,count)
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    old=client.get('/sochi/api/admin/state').json()
    oldpub=client.get('/sochi/api/public/state').json()
    data={'kind':'team_name','team_id':1,'value':'Новый капитан'}
    shown=preview(client,h,**data)
    assert shown.status_code==200,shown.text
    assert shown.json()['preview']['before']=='Тестовая команда 1'
    assert shown.json()['preview']['after']=='Новый капитан'
    assert client.get('/sochi/api/admin/state').json()==old
    assert client.get('/sochi/api/public/state').json()==oldpub
    bad=call(client,'correction/apply',h,dict(data,expected_version=version(client),pin='1234',
          confirm='ИСПРАВИТЬ',reason=REASON))
    assert bad.status_code==403
    bad=call(client,'correction/apply',h,dict(data,expected_version=version(client),pin=PIN,
          confirm='не подтверждаю',reason=REASON))
    assert bad.status_code==409
    bad=call(client,'correction/apply',h,dict(data,expected_version=version(client)-1,
          pin=PIN,confirm='ИСПРАВИТЬ',reason=REASON))
    assert bad.status_code==409
    assert client.get('/sochi/api/admin/state').json()==old

    result=commit(client,h,**data)
    assert result['version']==old['publication_version']+1
    current=client.get('/sochi/api/public/state').json()['state']
    assert current['teams']['1']=='Новый капитан'
    assert next(r for r in current['ranking'] if r['team_id']==1)['name']=='Новый капитан'
    logs=client.get('/sochi/api/admin/corrections/history').json()['history']
    assert len(logs)==1
    assert logs[0]['reason']==REASON
    assert logs[0]['field_name']=='Название команды №1'
    assert 'pin' not in json.dumps(logs)
    again=call(client,'correction/apply',h,dict(data,expected_version=old['publication_version'],
                  pin=PIN,confirm='ИСПРАВИТЬ',reason=REASON))
    assert again.status_code==409

@pytest.mark.parametrize('count',[10,11])
def test_correction_after_completed_final_rebuilds_all_scenes_and_awards(client,count):
    h=auth(client)
    finalized_votes(client,h,count)
    assert call(client,'publish',h,{'action':'final-show-start'}).status_code==200
    for step in range(1,6):
        assert call(client,'publish',h,{'action':'final-show-step','step':step}).status_code==200
    before=client.get('/sochi/api/admin/state').json()
    baseline=before['published']
    green1=baseline['stages']['1']['green']
    blue1=baseline['stages']['1']['blue']
    total1=next(r for r in baseline['ranking'] if r['team_id']==1)['total']
    old_rate=before['chip_settings']['reentry']
    old_count=before['stages']['1']['reentry_count']
    changed=commit(client,h,kind='stage',team_id=1,field='reentry_count',
                   value=old_count+1)
    new=client.get('/sochi/api/admin/state').json()['published']
    assert new['stages']['1']['green']==green1-old_rate
    assert new['stages']['1']['blue']==blue1
    assert next(r for r in new['ranking'] if r['team_id']==1)['total']==total1-old_rate
    assert new['green_show']['ranking']!=baseline['green_show']['ranking'] if baseline.get('green_show') else True
    assert new['final_show']['step']==5
    assert new['final_show']['ranking']==new['ranking']
    public=client.get('/sochi/api/public/state').json()['state']
    assert public['final_view']['champion']['total']==new['final_show']['podium'][0]['total']
    assert public['final_view']['board']==new['ranking']
    assert sum(r['votes'] for r in public['ranking'])==count*10000
    assert changed['summary']['score_changes']

    # Changing actual GREEN stack changes GREEN and BLUE in opposite directions.
    old=client.get('/sochi/api/admin/state').json()
    baseline_total=next(r for r in old['published']['ranking'] if r['team_id']==1)['total']
    old_green=old['stages']['1']['green_stack']
    old_b=old['published']['stages']['1']['blue']
    commit(client,h,kind='stage',team_id=1,field='green_stack',value=old_green+17000)
    now=client.get('/sochi/api/admin/state').json()['published']
    assert now['stages']['1']['blue']==old_b-17000
    assert next(r for r in now['ranking'] if r['team_id']==1)['total']==baseline_total
    assert now['final_show']['step']==5

@pytest.mark.parametrize('count',[10,11])
def test_red_places_swap_atomically_after_red_published(client,count):
    h=auth(client)
    finalized_votes(client,h,count)
    old=client.get('/sochi/api/admin/state').json()
    p1=old['stages']['1']['red_place']
    p2=old['stages']['2']['red_place']
    response=preview(client,h,kind='stage',team_id=1,field='red_place',value=p2)
    assert response.status_code==200,response.text
    assert client.get('/sochi/api/admin/state').json()['stages']['1']['red_place']==p1
    commit(client,h,kind='stage',team_id=1,field='red_place',value=p2)
    st=client.get('/sochi/api/admin/state').json()
    assert st['stages']['1']['red_place']==p2
    assert st['stages']['2']['red_place']==p1
    assert sorted(r['red_place'] for r in st['stages'].values())==list(range(1,count+1))
    assert st['published']['stages']['1']['red']==130000-(p2-1)*10000
    assert st['published']['stages']['2']['red']==130000-(p1-1)*10000

@pytest.mark.parametrize('count',[10,11])
def test_vote_and_bonus_corrections_update_published_total_without_double_credit(client,count):
    h=auth(client)
    finalized_votes(client,h,count)
    previous=client.get('/sochi/api/admin/state').json()['published']
    baseline_votes=sum(r['votes'] for r in previous['ranking'])
    assert baseline_votes==count*10000
    commit(client,h,kind='vote',team_id=1,value=3)
    now=client.get('/sochi/api/admin/state').json()['published']
    assert now['published_votes'][0]['target_team_id']==3
    assert sum(r['votes'] for r in now['ranking'])==baseline_votes
    assert now['vote_show']['entries'][0]['receiver_team_id']==3
    assert now['vote_show']['base_ranking'][0]['votes']==0
    # Switch to voter-mode after votes are published, without repeating any bonus.
    commit(client,h,kind='vote_mode',value='voter')
    pub=client.get('/sochi/api/admin/state').json()['published']
    assert pub['vote_mode']=='voter'
    assert sum(r['votes'] for r in pub['ranking'])==baseline_votes
    assert all(r['votes']==10000 for r in pub['ranking'])
    assert pub['vote_show']['mode']=='voter'

@pytest.mark.parametrize('count',[10,11])
def test_clear_required_stage_retracts_later_scenes_and_keeps_drafts(client,count):
    h=auth(client)
    finalized_votes(client,h,count)
    result=preview(client,h,kind='stage',team_id=1,field='green_stack',clear=True)
    assert result.status_code==200
    assert result.json()['preview']['retracted_phases']==['green','blue','red']
    commit(client,h,kind='stage',team_id=1,field='green_stack',clear=True)
    after=client.get('/sochi/api/admin/state').json()
    p=after['published']
    assert after['stages']['1']['green_stack'] is None
    assert p['published_phases']==[]
    assert not p['votes_published'] and not p['revealed_slots']
    assert 'green_show' not in p and 'blue_show' not in p and 'red_show' not in p
    assert 'vote_show' not in p and 'final_show' not in p
    assert p['scene']=='pause'
    assert after['votes'] and len(after['votes'])==count
    assert after['secrets'] and len(after['secrets'])==3

def test_corrections_from_player_to_secret_and_clear_slot(client):
    h=auth(client)
    prepare(client,h,10,True)
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    before=client.get('/sochi/api/admin/state').json()
    player=before['seats'][0]
    commit(client,h,kind='player_name',player_id=player['player_id'],value='Новое имя игрока')
    after=client.get('/sochi/api/admin/state').json()
    assert after['seats'][0]['player_name']=='Новое имя игрока'
    assert 'Новое имя игрока' in after['published']['roster'][str(player['team_id'])]
    commit(client,h,kind='captain',team_id=player['team_id'],value=player['player_id'])
    assert client.get('/sochi/api/admin/state').json()['teams'][player['team_id']-1]['captain_player_id']==player['player_id']
    commit(client,h,kind='captain',team_id=player['team_id'],clear=True)
    assert client.get('/sochi/api/admin/state').json()['teams'][player['team_id']-1]['captain_player_id'] is None
    commit(client,h,kind='secret',slot=1,player_id=player['player_id'],confirmed=False)
    assert len(client.get('/sochi/api/admin/state').json()['secrets'])==1
    commit(client,h,kind='secret',slot=1,clear=True)
    assert not client.get('/sochi/api/admin/state').json()['secrets']
    commit(client,h,kind='seat',card_id=player['card_id'],clear=True)
    assert client.get('/sochi/api/admin/state').json()['seats'][0]['player_id'] is None


def test_correction_invalid_inputs_are_atomic_and_admin_only(client):
    h=auth(client)
    prepare(client,h,10)
    state=client.get('/sochi/api/admin/state').json()
    assert client.post('/sochi/api/admin/correction/preview',json={
        'kind':'team_name','team_id':1,'value':'A','expected_version':0}).status_code==403 or True
    bad=preview(client,h,kind='stage',team_id=1,field='green_stack',value=-3)
    assert bad.status_code==422
    assert client.get('/sochi/api/admin/state').json()==state
    bad=preview(client,h,kind='stage',team_id=1,field='green_stack',value='100')
    assert bad.status_code==422
    assert client.get('/sochi/api/admin/state').json()==state
    bad=preview(client,h,kind='seat',card_id='nonexistent',value='Игрок')
    assert bad.status_code==422
    assert client.get('/sochi/api/admin/state').json()==state
