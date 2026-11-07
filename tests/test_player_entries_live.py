"""Live per-player re-entry/add-on and transparent team rollups."""
import sqlite3

from test_show import client, auth, call, prepare
from sochi_show.legacy_screen import render_legacy_screen
from sochi_show.server import app_factory


def players(client, headers):
    state = prepare(client, headers, 10, players=True)
    by_team = {}
    for row in state['seats']:
        by_team.setdefault(row['team_id'], []).append(row['player_id'])
    assert all(len(group) == 3 for group in by_team.values())
    return by_team


def change(client, headers, player_id, kind, **kwargs):
    return call(client, 'player-chips', headers, {
        'player_id':player_id, 'kind':kind, **kwargs})


def test_player_counters_roll_up_to_team_and_move_projection_live(client):
    h=auth(client)
    members=players(client,h)
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    p1,p2=members[1][:2]
    p3=members[2][0]
    assert change(client,h,p1,'reentry',delta=1).status_code==200
    assert change(client,h,p1,'reentry',delta=1).status_code==200
    assert change(client,h,p2,'reentry',delta=3).status_code==200
    assert change(client,h,p3,'reentry',count=2).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['stages']['1']['reentry_count']==5
    assert state['stages']['1']['reentry_chips']==150000
    assert state['stages']['2']['reentry_count']==2
    assert next(row for row in state['seats'] if row['player_id']==p1)['player_reentry_count']==2
    assert change(client,h,p2,'addon',count=2).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['stages']['1']['addon_count']==2
    assert state['stages']['1']['addon_chips']==100000
    assert 'green' not in state['published']['published_phases']
    public=client.get('/sochi/api/public/state').json()['state']
    assert public['team_reentries']['1']==5
    assert public['team_reentries']['2']==2
    assert public.get('stages')=={}  # No unpublished GREEN / BLUE stacks.
    assert call(client,'publish',h,{'action':'scene','scene':'teams'}).status_code==200
    legacy=client.get('/sochi/legacy').text
    names=public['teams']
    assert legacy.index(names['3']) < legacy.index(names['2']) < legacy.index(names['1'])
    assert 'RE-ENTRY: 5' in legacy
    assert 'RE-ENTRY: 2' in legacy


def test_manual_team_adjustment_is_preserved_during_next_player_entry(client):
    h=auth(client)
    members=players(client,h)
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    p1,p2=members[1][:2]
    assert change(client,h,p1,'reentry',count=2).status_code==200
    assert call(client,'stage',h,{'team_id':1,'reentry_count':7}).status_code==200
    assert change(client,h,p2,'reentry',delta=1).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['stages']['1']['reentry_count']==8
    assert state['stages']['1']['reentry_chips']==240000
    assert state['published']['team_reentries']['1']==8
    assert change(client,h,p2,'reentry',delta=-1).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['stages']['1']['reentry_count']==7
    assert next(x for x in state['seats'] if x['player_id']==p1)['player_reentry_count']==2


def test_entry_counters_can_be_recorded_before_setting_chip_rates(client):
    h=auth(client)
    members=players(client,h)
    p=members[1][0]
    assert change(client,h,p,'reentry',delta=1).status_code==200
    assert client.get('/sochi/api/admin/state').json()['stages']['1']['reentry_chips'] is None
    assert call(client,'chips-settings',h,{'reentry':25000}).status_code==200
    stage=client.get('/sochi/api/admin/state').json()['stages']['1']
    assert stage['reentry_count']==1 and stage['reentry_chips']==25000


def test_protect_published_green_reentries_but_allow_addons_until_blue(client):
    h=auth(client)
    members=players(client,h)
    p=members[1][0]
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    assert change(client,h,p,'reentry',delta=2).status_code==200
    rows=[{'team_id':i,'green_stack':300000, 'reentry_count':2 if i==1 else 0}
          for i in range(1,11)]
    assert call(client,'stages/bulk',h,{'phase':'green','teams':rows}).status_code==200
    published=call(client,'publish',h,{'action':'green'})
    assert published.status_code==200,published.text
    assert change(client,h,p,'reentry',delta=1).status_code==409
    assert change(client,h,p,'addon',delta=1).status_code==200
    state=client.get('/sochi/api/admin/state').json()
    assert state['stages']['1']['reentry_count']==2
    assert state['stages']['1']['addon_count']==1
    assert state['published']['team_reentries']['1']==2


def test_saved_captain_is_shown_immediately_on_published_team_board(client):
    h=auth(client)
    members=players(client,h)
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    pid=members[1][0]
    assert call(client,'team',h,{'team_id':1,'captain_player_id':pid}).status_code==200
    current=client.get('/sochi/api/public/state').json()['state']
    assert current['team_captains']['1'] == next(
        s['player_name'] for s in client.get('/sochi/api/admin/state').json()['seats']
        if s['player_id']==pid)
    assert call(client,'publish',h,{'action':'scene','scene':'teams'}).status_code==200
    assert 'КАПИТАН:' in client.get('/sochi/legacy').text


def test_counter_validation_is_safe_and_keeps_previous_data(client):
    h=auth(client)
    members=players(client,h)
    p1,p2=members[1][:2]
    assert change(client,h,p1,'reentry',delta=-1).status_code==422
    assert change(client,h,p1,'reentry',count=-1).status_code==422
    assert change(client,h,p1,'reentry',delta=1,count=1).status_code==422
    assert change(client,h,p1,'reentry',count=1.5).status_code==422
    assert change(client,h,p1,'reentry',count=1001).status_code==422
    assert change(client,h,p1,'invalid',delta=1).status_code==422
    assert change(client,h,999999,'reentry',delta=1).status_code==404
    assert all(s['reentry_count'] is None for s in client.get(
        '/sochi/api/admin/state').json()['stages'].values())


def test_old_database_adds_columns_without_losing_players(tmp_path):
    db=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE players(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, photo_path TEXT)')
        con.execute('INSERT INTO players(id,name,photo_path) VALUES (11,?,?)',('Saved player',None))
    app=app_factory(db_path=str(db),media_path=str(tmp_path/'media'),
        admin_password='A_very_long_test_password_12345',
        session_secret='A_very_long_random_secret_1234567890123456',secure_cookie=False)
    with sqlite3.connect(db) as con:
        r=con.execute('SELECT id,name,reentry_count,addon_count FROM players WHERE id=11').fetchone()
    assert r == (11,'Saved player',0,0)


def test_projector_and_admin_assets_reference_live_counters():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'sochi_show/static'
    screen=(root/'screen.js').read_text('utf-8')
    admin=(root/'admin.js').read_text('utf-8')
    assert '.sort((a,b)=>a.count-b.count' in screen
    assert 'team_captains' in screen
    assert "data-pc-action=" in admin
    assert "/sochi/api/admin/player-chips" in admin
