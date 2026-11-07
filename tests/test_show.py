import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sochi_show.core import EXPECTED_OCCUPANCY, green_points, blue_points, red_points, validate_seating
from sochi_show.server import app_factory


def approved_shape():
    """Artificial fixture to test importer only; NOT the real tournament seating!"""
    teams = [{'team_id': i, 'team': f'Тестовая команда {i}'} for i in range(1, 14)]
    variants = {}
    for n, distribution in EXPECTED_OCCUPANCY.items():
        missing = []
        for table, occupied in enumerate(distribution, 1):
            missing.extend([table] * (n - occupied))
        assert len(missing) == n or n == 10
        boxes = [0 for _ in distribution]
        cards = []
        for team_id in range(1, n + 1):
            for table in range(1, len(distribution) + 1):
                if n != 10 and table == missing[team_id - 1]:
                    continue
                boxes[table - 1] += 1
                cards.append({'card_id': f'{n}-T{team_id}-B{table}', 'team_id': team_id,
                              'table': table, 'box': boxes[table - 1], 'team': f'Тестовая команда {team_id}'})
        variants[str(n)] = {'cards': cards}
    return {'teams': teams, 'variants': variants}


@pytest.mark.parametrize('n', [10, 11, 12, 13])
def test_import_variants(n):
    doc = approved_shape()
    teams, cards = validate_seating(doc, n)
    assert len(teams) == n
    assert len(cards) == n * 3
    assert {c['table'] for c in cards} == set(range(1, 4 if n == 10 else 5))
    bad = json.loads(json.dumps(doc))
    bad['variants'][str(n)]['cards'][0]['box'] = bad['variants'][str(n)]['cards'][1]['box']
    bad['variants'][str(n)]['cards'][0]['table'] = bad['variants'][str(n)]['cards'][1]['table']
    with pytest.raises(ValueError):
        validate_seating(bad, n)


def test_scoring_math_and_negative():
    assert green_points(250_000, 300_000) == -50_000
    assert blue_points(200_000, 300_000, 150_000, 2) == -40_000
    assert blue_points(150_000, 200_000, 60_000, 0) == -10_000
    assert red_points(1, 13) == 130_000
    assert red_points(12, 13) == 20_000
    assert red_points(13, 13) == 10_000
    with pytest.raises(ValueError): blue_points(0, 0, 0, 4)


@pytest.fixture
def client(tmp_path):
    app = app_factory(db_path=str(tmp_path / 'show.sqlite3'),
                      media_path=str(tmp_path / 'media'),
                      admin_password='A_real_long_test_password_123',
                      session_secret='A_very_long_random_testing_session_secret_9876',secure_cookie=False)
    with TestClient(app) as c:
        yield c


def auth(client):
    assert client.post('/sochi/api/admin/login', json={'password': 'A_real_long_test_password_123'}).status_code == 200
    state = client.get('/sochi/api/admin/state').json()
    return {'X-CSRF-Token': state['csrf']}


def call(client, endpoint, headers, data):
    return client.post('/sochi/api/admin/' + endpoint, headers=headers, json=data)


def prepare(client, headers, n=10, players=False):
    assert call(client, 'seating', headers, {'team_count': n, 'document': approved_shape()}).status_code == 200
    # Historical test fixtures used zero-cost initial entries. Production now
    # requires the organiser to explicitly choose a per-player entry rate.
    assert call(client,'chips-settings',headers,{'entry':0}).status_code == 200
    state = client.get('/sochi/api/admin/state').json()
    if players:
        for seat in state['seats']:
            assert call(client, 'player', headers,
                        {'card_id': seat['card_id'], 'name': f'Игрок-{seat["card_id"]}'}).status_code == 200
    return client.get('/sochi/api/admin/state').json()


def test_protected_admin_and_csrf(client):
    assert client.get('/sochi/api/admin/state').status_code == 401
    assert client.post('/sochi/api/admin/seating', json={'team_count': 10}).status_code == 401
    headers = auth(client)
    assert client.post('/sochi/api/admin/seating', json={'team_count': 10}).status_code == 403
    assert client.get('/sochi/api/public/state').json()['state']['teams'] == {}


def test_published_not_draft(client):
    h = auth(client)
    prepare(client, h)
    assert call(client, 'team', h, {'team_id': 1, 'display_name': 'Новое имя'}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['teams'] == {}
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    p = client.get('/sochi/api/public/state').json()['state']
    assert p['teams']['1'] == 'Новое имя'
    assert call(client, 'team', h, {'team_id': 1, 'display_name': 'Тайный черновик'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'intro'}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['teams']['1'] == 'Новое имя'
    assert call(client, 'publish', h, {'action': 'name', 'team_id': 1}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['teams']['1'] == 'Тайный черновик'


def fill_stages(client, h, n):
    assert call(client, 'chips-settings', h, {'reentry': 60000, 'addon': 50000}).status_code == 200
    for i in range(1, n + 1):
        stage = {'team_id': i, 'green_stack': 300000 if i == 1 else 200000,
                 'reentry_count': 2, 'blue_stack': 330000,
                 'addon_count': 1, 'survivors': 2, 'red_place': i}
        result = call(client, 'stage', h, stage)
        assert result.status_code == 200, result.text


@pytest.mark.parametrize('n', [10, 11, 12, 13])
def test_scores_votes_and_secret_privacy(client, n):
    h = auth(client)
    a = prepare(client, h, n, True)
    players = [s for s in a['seats'] if s['player_id']]
    fill_stages(client, h, n)
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    for phase in ('green', 'blue', 'red'):
        res = call(client, 'publish', h, {'action': phase})
        assert res.status_code == 200, res.text
    pub = client.get('/sochi/api/public/state').json()['state']
    assert pub['ranking'][0]['green'] == 180_000
    # BLUE for team 1 uses 300k actual GREEN stack, not 180k GREEN points.
    assert next(x for x in pub['ranking'] if x['team_id'] == 1)['blue'] == -10_000
    # Change draft without publishing: it must not change the score.
    assert call(client, 'stage', h, {'team_id': 1, 'green_stack': 1}).status_code == 200
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'red'}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['ranking'] == pub['ranking']
    selected = players[:3]
    for idx, seat in enumerate(selected, 1):
        assert call(client, 'secret', h, {'slot': idx, 'player_id': seat['player_id'],
                                        'knockout_team_id': 2, 'knockout_player_id': next(s['player_id'] for s in players if s['team_id'] == 2), 'confirmed': True}).status_code == 200
    for i in range(1, n + 1):
        assert call(client, 'vote', h, {'voter_team_id': i,
                                      'target_team_id': 2 if i != 2 else 1}).status_code == 200
    # Names in public JSON before revelation never include private names or ID of secrets.
    raw = client.get('/sochi/api/public/state').text
    assert 'knockout_name' not in raw and 'jack_team_id' not in raw
    assert 'green_stack_actual' not in raw
    assert 'revealed_secrets' in raw and '"revealed_secrets":[]' in raw
    assert '"published_votes":[]' in raw
    assert call(client, 'publish', h, {'action': 'reveal', 'slot': 2}).status_code == 409
    for slot in (1, 2, 3):
        assert call(client, 'publish', h, {'action': 'reveal', 'slot': slot}).status_code == 200
        assert call(client, 'publish', h, {'action': 'reveal', 'slot': slot}).status_code == 409
    pub2 = client.get('/sochi/api/public/state').json()['state']
    assert sum(r['secret'] for r in pub2['ranking']) == 30_000
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 200
    pub3 = client.get('/sochi/api/public/state').json()['state']
    assert sum(r['votes'] for r in pub3['ranking']) == n * 10_000
    assert call(client, 'vote-mode', h, {'mode': 'voter'}).status_code == 409


def test_photo_freeze_public(client):
    h = auth(client)
    state = prepare(client, h, 10, True)
    player = next(s for s in state['seats'] if s['team_id'] == 1)
    pid = player['player_id']
    assert client.get('/sochi/api/public/photo/' + str(pid)).status_code == 404
    assert call(client, 'team', h, {'team_id': 1, 'captain_player_id': pid}).status_code == 200
    im = Image.new('RGB', (300, 240), color=(70, 95, 118))
    stream = io.BytesIO(); im.save(stream, 'PNG')
    res = client.post(f'/sochi/api/admin/photo/{pid}',headers=h,
                      files={'file': ('portrait.png', stream.getvalue(), 'image/png')})
    assert res.status_code == 200, res.text
    assert client.get('/sochi/api/public/photo/' + str(pid)).status_code == 404
    assert call(client, 'publish', h, {'action': 'captains'}).status_code == 200
    image1 = client.get('/sochi/api/public/photo/' + str(pid))
    assert image1.status_code == 200 and image1.content
    im = Image.new('RGB', (300, 240), color=(250, 55, 11))
    stream = io.BytesIO(); im.save(stream, 'PNG')
    assert client.post(f'/sochi/api/admin/photo/{pid}',headers=h,
                       files={'file': ('new.png', stream.getvalue(), 'image/png')}).status_code == 200
    assert client.get('/sochi/api/public/photo/' + str(pid)).content == image1.content
    assert call(client, 'publish', h, {'action': 'refresh-photo', 'player_id': pid}).status_code == 200
    assert client.get('/sochi/api/public/photo/' + str(pid)).content != image1.content


def test_revealed_correction_recomputes_once(client):
    h = auth(client)
    s = prepare(client, h, 10, True)
    seats = [x for x in s['seats'] if x['player_id']]
    p1, p2 = seats[0], seats[1]
    killer = next(x for x in seats if x['team_id'] == 2)
    for idx, seat in enumerate(seats[:3], 1):
        assert call(client, 'secret', h, {'slot': idx, 'player_id': seat['player_id'],
                    'knockout_team_id': 2, 'knockout_player_id': killer['player_id'], 'confirmed': True}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    # The tested correction applies to an already valid published RED show;
    # direct reveal is intentionally forbidden before any scored phase.
    assert call(client, 'publish', h, {'action': 'reveal', 'slot': 1}).status_code == 409
    assert call(client, 'chips-settings', h, {'reentry':30000,'addon':50000}).status_code == 200
    for tid in range(1,11):
        assert call(client,'stage',h,{'team_id':tid,'green_stack':500000,
            'reentry_count':0,'blue_stack':750000,'addon_count':0,
            'survivors':0,'red_place':tid}).status_code == 200
    for phase in ('green','blue','red'):
        assert call(client,'publish',h,{'action':phase}).status_code == 200
    assert call(client, 'publish', h, {'action': 'reveal', 'slot': 1}).status_code == 200
    raw = client.get('/sochi/api/public/state').json()['state']
    assert sum(x['secret'] for x in raw['ranking']) == 10000
    # Cannot accidentally publish a correction without organizer confirmation.
    payload = {'slot': 1, 'player_id': p1['player_id'], 'knockout_team_id': 3,
               'knockout_player_id': next(x for x in seats if x['team_id'] == 3)['player_id'], 'confirmed': True}
    assert call(client, 'secret-correction', h, payload).status_code == 409
    payload['confirm_correction'] = True
    assert call(client, 'secret-correction', h, payload).status_code == 409
    # Correctly protected alternate path: reason, current version, PIN and phrase.
    payload.pop('confirm_correction')
    payload['kind'] = 'secret'
    payload['expected_version'] = client.get('/sochi/api/admin/state').json()['publication_version']
    payload['reason'] = 'Исправление раскрытого Secret Jack'
    payload['pin'] = 'A_real_long_test_password_123'
    payload['confirm'] = 'ИСПРАВИТЬ'
    assert call(client, 'correction/apply', h, payload).status_code == 200
    state = client.get('/sochi/api/public/state').json()['state']
    assert sum(x['secret'] for x in state['ranking']) == 10000
    assert next(x for x in state['ranking'] if x['team_id'] == 3)['secret'] == 10000
    assert next(x for x in state['ranking'] if x['team_id'] == 2)['secret'] == 0


def test_stage_bulk_and_self_vote(client):
    h=auth(client)
    prepare(client, h)
    assert call(client, 'chips-settings', h, {'reentry': 30000}).status_code == 200
    rows=[{'team_id':i,'green_stack':i*10000,'reentry_count':0} for i in range(1,11)]
    assert call(client, 'stages/bulk', h, {'phase':'green','teams':rows}).status_code == 200
    assert call(client, 'publish', h, {'action':'teams'}).status_code == 200
    assert call(client, 'publish', h, {'action':'green'}).status_code == 200
    bad=rows[:]
    bad[0]=dict(bad[0],green_stack=-1)
    assert call(client, 'stages/bulk', h, {'phase':'green','teams':bad}).status_code == 422
    assert call(client, 'vote', h, {'voter_team_id':1,'target_team_id':1}).status_code == 422
    assert client.get('/sochi/api/public/state').json()['state']['ranking'][0]['green']==100000


def test_short_pin_login_and_bruteforce_limit(tmp_path):
    app = app_factory(db_path=str(tmp_path / 'pin.sqlite3'),
                      media_path=str(tmp_path / 'media'),
                      admin_password='7392',
                      session_secret='Another_long_random_testing_session_secret_9876',
                      secure_cookie=False)
    with TestClient(app) as c:
        assert c.post('/sochi/api/admin/login', json={'password': '7392'}).status_code == 200
        assert c.get('/sochi/api/admin/state').status_code == 200

    # An attacker must not be able to exhaustively guess a four-digit PIN.
    app2 = app_factory(db_path=str(tmp_path / 'blocked.sqlite3'),
                       media_path=str(tmp_path / 'other-media'),
                       admin_password='7392',
                       session_secret='Another_long_random_testing_session_secret_9876',
                       secure_cookie=False)
    with TestClient(app2) as c:
        for guess in range(8):
            assert c.post('/sochi/api/admin/login', json={'password': f'{guess:04d}'}).status_code == 401
        assert c.post('/sochi/api/admin/login', json={'password': '7392'}).status_code == 429


@pytest.mark.parametrize('bad_password', ['123', '12345', '12a4', 'abcd', ''])
def test_invalid_short_admin_password_rejected(tmp_path, bad_password):
    with pytest.raises(RuntimeError, match='4-digit PIN'):
        app_factory(db_path=str(tmp_path / 'invalid.sqlite3'),
                    media_path=str(tmp_path / 'media'),
                    admin_password=bad_password,
                    session_secret='Another_long_random_testing_session_secret_9876',
                    secure_cookie=False)


def test_admin_operator_guide_and_daylight_theme(client):
    html = client.get('/sochi/admin')
    assert html.status_code == 200
    assert 'Как управлять шоу — по шагам' in html.text
    assert 'workflow-guide' in html.text
    for name in ('control-panel', 'seating-panel', 'teams-panel', 'scores-panel',
                 'secrets-panel', 'votes-panel', 'review-panel'):
        assert f'id="{name}"' in html.text
    assert 'это не отдельный деморежим' in html.text
    js = client.get('/sochi/static/admin.js')
    assert js.status_code == 200
    assert 'installModuleLayout();' in js.text
    assert 'updateWorkflow();' in js.text
    css = client.get('/sochi/static/style.css')
    assert css.status_code == 200
    assert '.admin .guide-panel' in css.text
    assert '.admin .module-accordion' in css.text
    assert '.projector' in css.text


def test_configured_chip_rates_are_multiplied_and_frozen(client):
    h=auth(client)
    prepare(client,h,10)
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    s=client.get('/sochi/api/admin/state').json()
    assert s['chip_settings']=={'reentry':30000,'addon':50000,'entry':0}
    assert call(client,'stage',h,{'team_id':1,'green_stack':300000,'reentry_count':2,
                                  'blue_stack':410000,'addon_count':3,'survivors':2}).status_code==200
    s=client.get('/sochi/api/admin/state').json()['stages']['1']
    assert s['reentry_chips']==60000 and s['addon_chips']==150000
    # Changing an unpublished rate recomputes team draft chip totals.
    assert call(client,'chips-settings',h,{'reentry':40000}).status_code==200
    assert client.get('/sochi/api/admin/state').json()['stages']['1']['reentry_chips']==80000
    assert call(client,'publish',h,{'action':'teams'}).status_code==200
    green=[{'team_id':i,'green_stack':300000,'reentry_count':2 if i==1 else 0} for i in range(1,11)]
    assert call(client,'stages/bulk',h,{'phase':'green','teams':green}).status_code==200
    assert call(client,'publish',h,{'action':'green'}).status_code==200
    published=client.get('/sochi/api/public/state').json()['state']
    assert next(r for r in published['ranking'] if r['team_id']==1)['green']==220000
    assert call(client,'chips-settings',h,{'reentry':50000}).status_code==409
    assert client.get('/sochi/api/public/state').json()['state']['ranking']==published['ranking']

    blue=[{'team_id':i,'blue_stack':410000,'addon_count':3 if i==1 else 0,'survivors':2} for i in range(1,11)]
    assert call(client,'stages/bulk',h,{'phase':'blue','teams':blue}).status_code==200
    assert call(client,'publish',h,{'action':'blue'}).status_code==200
    current=client.get('/sochi/api/public/state').json()['state']
    assert next(r for r in current['ranking'] if r['team_id']==1)['blue']==-30000
    assert call(client,'chips-settings',h,{'addon':90000}).status_code==409
    assert call(client,'stage',h,{'team_id':1,'addon_count':2}).status_code==200
    assert client.get('/sochi/api/admin/state').json()['stages']['1']['addon_chips']==100000
    assert client.get('/sochi/api/public/state').json()['state']['ranking']==current['ranking']


def test_chips_settings_validation_and_manual_amounts_forbidden(client):
    h=auth(client)
    prepare(client,h,10)
    assert call(client,'stage',h,{'team_id':1,'reentry_count':0}).status_code==409
    for value in (0,-1,1.5,'30000',1000000001):
        assert call(client,'chips-settings',h,{'reentry':value}).status_code==422
    assert call(client,'chips-settings',h,{'reentry':30000,'addon':50000}).status_code==200
    assert call(client,'stage',h,{'team_id':1,'reentry_chips':90000}).status_code==422
    assert call(client,'stage',h,{'team_id':1,'addon_chips':90000}).status_code==422
    assert call(client,'stage',h,{'team_id':1,'reentry_count':1001}).status_code==422
    assert call(client,'stage',h,{'team_id':1,'addon_count':1001}).status_code==422
    assert call(client,'stage',h,{'team_id':1,'reentry_count':0,'addon_count':0}).status_code==200
    values=client.get('/sochi/api/admin/state').json()['stages']['1']
    assert values['reentry_chips']==0 and values['addon_chips']==0


def test_existing_stage_db_migrates_addon_count_without_removing_data(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE stages (team_id INTEGER PRIMARY KEY,green_stack INTEGER,'
                   'reentry_chips INTEGER,reentry_count INTEGER,blue_stack INTEGER,'
                   'addon_chips INTEGER,survivors INTEGER,red_place INTEGER)')
        db.execute('INSERT INTO stages(team_id,green_stack,reentry_chips,reentry_count) '
                   'VALUES (1,250000,120000,2)')
    app=app_factory(db_path=str(path),media_path=str(tmp_path/'media'),
                    admin_password='A_real_long_test_password_123',
                    session_secret='A_very_long_random_testing_session_secret_9876',
                    secure_cookie=False)
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
    with sqlite3.connect(path) as db:
        row=db.execute('SELECT green_stack,reentry_chips,reentry_count,addon_count '
                       'FROM stages WHERE team_id=1').fetchone()
    assert row==(250000,120000,2,None)


def test_chips_ui_is_count_only(client):
    html=client.get('/sochi/admin').text
    assert 'id="chips-settings-modal"' in html
    assert 'id="open-chips-settings"' in html
    assert '<th>Re-entry, шт.</th>' in html
    assert '<th>Add-on, шт.</th>' in html
    assert '<th>Re-entry фишки</th>' not in html
    assert '<th>Add-on фишки</th>' not in html
    js=client.get('/sochi/static/admin.js').text
    assert "'reentry_count','blue_stack','addon_count'" in js
    assert "api('/sochi/api/admin/chips-settings'" in js
