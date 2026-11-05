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
    for i in range(1, n + 1):
        stage = {'team_id': i, 'green_stack': 300000 if i == 1 else 200000,
                 'reentry_chips': 120000, 'reentry_count': 2, 'blue_stack': 330000,
                 'addon_chips': 50000, 'survivors': 2, 'red_place': i}
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
    assert call(client, 'publish', h, {'action': 'reveal', 'slot': 1}).status_code == 200
    raw = client.get('/sochi/api/public/state').json()['state']
    assert sum(x['secret'] for x in raw['ranking']) == 10000
    # Cannot accidentally publish a correction without organizer confirmation.
    payload = {'slot': 1, 'player_id': p1['player_id'], 'knockout_team_id': 3,
               'knockout_player_id': next(x for x in seats if x['team_id'] == 3)['player_id'], 'confirmed': True}
    assert call(client, 'secret-correction', h, payload).status_code == 409
    payload['confirm_correction'] = True
    assert call(client, 'secret-correction', h, payload).status_code == 200
    state = client.get('/sochi/api/public/state').json()['state']
    assert sum(x['secret'] for x in state['ranking']) == 10000
    assert next(x for x in state['ranking'] if x['team_id'] == 3)['secret'] == 10000
    assert next(x for x in state['ranking'] if x['team_id'] == 2)['secret'] == 0


def test_stage_bulk_and_self_vote(client):
    h=auth(client)
    prepare(client, h)
    rows=[{'team_id':i,'green_stack':i*10000,'reentry_chips':0,'reentry_count':0} for i in range(1,11)]
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
