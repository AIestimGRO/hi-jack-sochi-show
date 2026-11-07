"""BLUE scoring conversion after chip-ranking reveal. No spoilers, full audit, fair RED."""
import pytest
from test_show import auth, call, prepare, fill_stages, client
from test_blue_show import setup_stages
from sochi_show.core import blue_points_from_policy, green_points


def apply_policy(client,h,policy):
    state=client.get('/sochi/api/admin/state').json()
    payload={'kind':'blue_policy','value':policy,'expected_version':state['publication_version']}
    prv=call(client,'correction/preview',h,payload)
    assert prv.status_code==200,prv.text
    assert client.get('/sochi/api/admin/state').json()['publication_version']==payload['expected_version']
    body={**payload,'pin':'A_real_long_test_password_123',
          'confirm':'ИСПРАВИТЬ','reason':'Сохраняем конкуренцию за финальным столом'}
    result=call(client,'correction/apply',h,body)
    assert result.status_code==200,result.text
    return result.json()


def completed_blue(client,h,count):
    setup_stages(client,h,count)
    pub=call(client,'publish',h,{'action':'blue','show_mode':'cinematic'})
    assert pub.status_code==200,pub.text
    for step in range(1,count+2):
        r=call(client,'publish',h,{'action':'blue-show-step','step':step})
        assert r.status_code==200,r.text
    return client.get('/sochi/api/admin/state').json()['published']


@pytest.mark.parametrize('count',[10,11])
@pytest.mark.parametrize('mode',['chips','scale','places'])
def test_blue_conversion_is_private_until_explicit_reveal_then_flows_to_red(client,count,mode):
    h=auth(client)
    before=completed_blue(client,h,count)
    old_net={str(i):before['stages'][str(i)]['green']+
             before['stages'][str(i)]['blue'] for i in range(1,count+1)}
    policy={'mode':mode,'percent':10,'place_points':[130000-i*10000 for i in range(count)]}
    apply_policy(client,h,policy)
    admin=client.get('/sochi/api/admin/state').json()['published']
    assert admin['blue_policy']['mode']==mode
    assert admin['blue_policy']['revealed'] is False
    assert len(admin['blue_policy']['points'])==count
    expected=blue_points_from_policy({int(k):v for k,v in old_net.items()},policy,count)
    assert admin['blue_policy']['points']==expected
    for i in range(1,count+1):
        assert admin['stages'][str(i)]['green']==before['stages'][str(i)]['green']
        assert admin['stages'][str(i)]['blue']==before['stages'][str(i)]['blue']
        row=next(r for r in admin['ranking'] if r['team_id']==i)
        assert row['chip_net']==old_net[str(i)]
        assert row['base_points']==expected[str(i)]
        assert row['total']==expected[str(i)]

    private=client.get('/sochi/api/public/state').json()['state']
    assert private['blue_policy']=={'mode':'pending','revealed':False}
    assert private['ranking']==[] and private['stages']=={}
    assert private['blue_view']['step']==count+1
    assert 'points' not in private['blue_policy']
    assert all('award' not in r for r in private['blue_view']['revealed'])
    # No bypass through RED.
    assert call(client,'publish',h,{'action':'red'}).status_code==409
    done=call(client,'publish',h,{'action':'blue-policy-reveal'})
    assert done.status_code==200,done.text
    visible=client.get('/sochi/api/public/state').json()['state']
    assert visible['scene']=='blue_show'
    assert visible['blue_policy']=={'mode':mode,'revealed':True}
    assert visible['blue_view']['points_revealed'] is True
    for row in visible['blue_view']['revealed']:
        assert row['award']==expected[str(row['team_id'])]
        assert row['total']==old_net[str(row['team_id'])]

    for tid in range(1,count+1):
        assert call(client,'stage',h,{'team_id':tid,'red_place':tid}).status_code==200
    assert call(client,'publish',h,{'action':'red','show_mode':'cinematic'}).status_code==200
    red=client.get('/sochi/api/admin/state').json()['published']
    for row in red['red_show']['ranking']:
        assert row['base_points']==expected[str(row['team_id'])]
        assert row['total']==expected[str(row['team_id'])]+row['red']
    assert sum(r['red'] for r in red['ranking'])==sum(130000-i*10000 for i in range(count))


@pytest.mark.parametrize('count',[10,11])
def test_conversion_must_wait_for_end_of_blue_and_is_pin_protected(client,count):
    h=auth(client)
    setup_stages(client,h,count)
    assert call(client,'publish',h,{'action':'blue','show_mode':'cinematic'}).status_code==200
    v=client.get('/sochi/api/admin/state').json()['publication_version']
    payload={'kind':'blue_policy','value':{'mode':'places','place_points':[130000-i*10000 for i in range(count)]},'expected_version':v}
    assert call(client,'correction/preview',h,payload).status_code==409
    for step in range(1,count+2):
        assert call(client,'publish',h,{'action':'blue-show-step','step':step}).status_code==200
    v=client.get('/sochi/api/admin/state').json()['publication_version']
    payload['expected_version']=v
    assert call(client,'correction/preview',h,payload).status_code==200
    assert call(client,'correction/apply',h,{**payload,'pin':'wrong',
      'confirm':'ИСПРАВИТЬ','reason':'Тест решения после блю'}).status_code==403
    invalid={'mode':'places','place_points':[130000,140000]+[100000]*(count-2)}
    assert call(client,'correction/preview',h,{**payload,'value':invalid}).status_code==422


def test_entry_is_deducted_per_player_and_legacy_default_is_safe(client):
    h=auth(client)
    prepare(client,h,10)
    # Before explicitly setting entry, old behavior stays compatible.
    assert green_points(145000,150000)==-5000
    assert green_points(145000,150000,50000)==-55000
    assert call(client,'chips-settings',h,{'entry':50000,'reentry':50000,'addon':100000}).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['chip_settings']=={'entry':50000,'reentry':50000,'addon':100000}
    for tid in range(1,11):
        assert call(client,'stage',h,{'team_id':tid,'green_stack':500000+tid*10000,
                                      'reentry_count':2,'blue_stack':900000+tid*10000,
                                      'addon_count':1,'survivors':1}).status_code==200
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    assert call(client,'publish',h,{'action':'green'}).status_code==200
    state=client.get('/sochi/api/admin/state').json()['published']
    assert state['stages']['1']['green']==510000-100000-150000
    assert call(client,'publish',h,{'action':'blue'}).status_code==200
    state=client.get('/sochi/api/admin/state').json()['published']
    r=state['stages']['1']
    assert r['blue']==(910000-510000-100000+5000)
    assert r['green']+r['blue']==910000-150000-100000-100000+5000


def test_blank_seat_name_is_clearable_with_unpublished_cards(client):
    h=auth(client)
    d=prepare(client,h,10,players=True)
    first=d['seats'][0]
    assert first['player_id']
    result=call(client,'player',h,{'card_id':first['card_id'],'name':'',
                                    'confirm_rebind':True})
    assert result.status_code==200,result.text
    updated=client.get('/sochi/api/admin/state').json()
    seat=next(r for r in updated['seats'] if r['card_id']==first['card_id'])
    assert seat['player_id'] is None and seat['player_name'] is None
    assert call(client,'player',h,{'card_id':first['card_id'],'name':' ',
                                    'confirm_rebind':False}).status_code==200


def test_blue_points_ties_share_place_points():
    chips={1:100000,2:100000,3:50000}
    d=blue_points_from_policy(chips,{'mode':'places','place_points':[130000,120000,110000]},3)
    assert d=={'1':130000,'2':130000,'3':110000}


@pytest.mark.parametrize('count',[10,11])
def test_blue_places_use_only_net_chips_survivor_bonus_applies_after_conversion(client,count):
    h=auth(client)
    setup_stages(client,h,count)
    # GREEN stacks are 110k for team1 and 120k for team2. Make their
    # raw BLUE results 450k and 460k while team1 earns 3 survivor bonuses.
    assert call(client,'stage',h,{'team_id':1,'blue_stack':450000,'survivors':3}).status_code==200
    assert call(client,'stage',h,{'team_id':2,'blue_stack':460000,'survivors':0}).status_code==200
    assert call(client,'publish',h,{'action':'blue','show_mode':'cinematic'}).status_code==200
    p=client.get('/sochi/api/admin/state').json()['published']
    assert p['stages']['1']['blue_net_chips']==450000
    assert p['stages']['1']['survivor_bonus']==15000
    assert p['stages']['2']['blue_net_chips']==460000
    assert p['stages']['2']['survivor_bonus']==0
    ranked={r['team_id']:r for r in p['blue_show']['ranking']}
    assert ranked[2]['place']<ranked[1]['place']  # not affected by bonuses
    assert ranked[1]['award']==465000
    assert ranked[1]['total']==450000  # on-screen raw NET, not earned points
    assert ranked[2]['award']==460000

    for step in range(1,count+2):
        assert call(client,'publish',h,{'action':'blue-show-step','step':step}).status_code==200
    policy={'mode':'places','place_points':[130000-i*10000 for i in range(count)]}
    apply_policy(client,h,policy)
    p=client.get('/sochi/api/admin/state').json()['published']
    ranked={r['team_id']:r for r in p['blue_show']['ranking']}
    assert ranked[2]['place']<ranked[1]['place']
    assert ranked[1]['award']==policy['place_points'][ranked[1]['place']-1]+15000
    assert ranked[2]['award']==policy['place_points'][ranked[2]['place']-1]
    assert p['blue_policy']['points']['1']==policy['place_points'][ranked[1]['place']-1]
    assert next(r for r in p['ranking'] if r['team_id']==1)['total']==ranked[1]['award']
    assert next(r for r in p['ranking'] if r['team_id']==2)['total']==ranked[2]['award']

    # Already-published BLUE can be corrected without changing chip rankings
    # through the protected workflow. The 5k is never counted twice.
    from test_protected_corrections import commit
    commit(client,h,kind='stage',team_id=1,field='survivors',value=2)
    corrected=client.get('/sochi/api/admin/state').json()['published']
    assert corrected['stages']['1']['blue_net_chips']==450000
    assert corrected['stages']['1']['survivor_bonus']==10000
    assert next(r for r in corrected['ranking'] if r['team_id']==1)['total']==ranked[1]['award']-5000
