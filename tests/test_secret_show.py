"""SECRET JACK SHOW: safe first reveal, replay and single 10k bonus per confirmed KO."""
import json
import pytest
from test_show import auth, call, prepare, fill_stages, client


def ready(client, h, n):
    state = prepare(client, h, n, True)
    players = [s for s in state['seats'] if s['player_id']]
    fill_stages(client, h, n)
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    for phase in ('green', 'blue', 'red'):
        assert call(client, 'publish', h, {'action': phase}).status_code == 200
    assert len(players) >= 3
    killer = next(s for s in players if s['team_id'] == 2)
    # 1st and 3rd confirmed, 2nd survived (no point awards).
    for i, s in enumerate(players[:3], 1):
        body={'slot': i, 'player_id': s['player_id'], 'confirmed': i != 2}
        if i != 2:
            body.update({'knockout_team_id': 2, 'knockout_player_id': killer['player_id']})
        result = call(client, 'secret', h, body)
        assert result.status_code == 200, result.text
    return players


@pytest.mark.parametrize('n', [10, 11])
def test_secret_show_complete_and_replay_do_not_double_award(client, n):
    h = auth(client)
    players = ready(client, h, n)
    names = [s['player_name'] for s in players[:3]]
    start = call(client, 'publish', h, {'action': 'secret-show-start'})
    assert start.status_code == 200, start.text
    state = client.get('/sochi/api/public/state').json()['state']
    assert state['scene'] == 'secret_show'
    assert state['secret_view'] == {
        'step': 0, 'revealed_count': 0, 'max_step': 0,
        'revealed': [], 'summary': False}
    assert state['ranking'] == [] and state['stages'] == {}
    assert not state['revealed_secrets']
    for name in names:
        assert name not in json.dumps(state, ensure_ascii=False)
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 1}).status_code == 422
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 409

    for slot in (1, 2, 3):
        assert call(client, 'publish', h, {'action': 'reveal', 'slot': slot}).status_code == 200
        show = client.get('/sochi/api/public/state').json()['state']
        assert show['scene'] == 'secret_show'
        assert show['secret_view']['step'] == slot
        assert show['secret_view']['revealed_count'] == slot
        assert len(show['revealed_secrets']) == slot
        assert len(show['secret_view']['revealed']) == slot
        assert show['ranking'] == []
        assert show['stages'] == {}
        assert show['secret_view']['revealed'][-1]['name'] == names[slot-1]
        assert all(name not in json.dumps(show, ensure_ascii=False) for name in names[slot:])
        assert call(client, 'publish', h, {'action': 'reveal', 'slot': slot}).status_code == 409
        assert call(client, 'publish', h, {'action': 'votes'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 4}).status_code == 200
    published = client.get('/sochi/api/public/state').json()['state']
    assert published['secret_view']['summary'] is True
    assert len(published['secret_view']['revealed']) == 3
    assert len(published['ranking']) == n
    assert sum(row['secret'] for row in published['ranking']) == 20000
    assert next(r for r in published['ranking'] if r['team_id'] == 2)['secret'] == 20000
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 5}).status_code == 422

    # Rehearsal again after all three published: not a single new chip credited.
    assert call(client, 'publish', h, {'action': 'secret-show-start'}).status_code == 200
    replay = client.get('/sochi/api/public/state').json()['state']
    assert replay['ranking'] == []
    assert replay['revealed_secrets'] == []
    assert replay['secret_view']['revealed_count'] == 3
    assert call(client, 'publish', h, {'action': 'reveal', 'slot': 1}).status_code == 409
    for step in (1, 2, 3, 4):
        assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': step}).status_code == 200
        visible = client.get('/sochi/api/public/state').json()['state']
        assert len(visible['revealed_secrets']) == min(step, 3)
        if step < 4:
            assert visible['ranking'] == []
    again = client.get('/sochi/api/public/state').json()['state']
    assert sum(row['secret'] for row in again['ranking']) == 20000
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 3}).status_code == 200
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 4}).status_code == 200


def test_secret_show_rejects_missing_roles_and_premature_start(client):
    h = auth(client)
    prepare(client, h, 10)
    assert call(client, 'publish', h, {'action': 'secret-show-start'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 1}).status_code == 409


def test_secret_show_blocks_vote_until_summary(client):
    h = auth(client)
    ready(client, h, 10)
    for team_id in range(1,11):
        target=2 if team_id != 2 else 1
        assert call(client, 'vote', h, {'voter_team_id': team_id,
                                       'target_team_id': target}).status_code == 200
    assert call(client, 'publish', h, {'action': 'secret-show-start'}).status_code == 200
    for slot in range(1,4):
        assert call(client, 'publish', h, {'action': 'reveal', 'slot': slot}).status_code == 200
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene','scene':'secrets'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'secret-show-step', 'step': 4}).status_code == 200
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'secret-show-start'}).status_code == 409
    state = client.get('/sochi/api/public/state').json()['state']
    assert state['votes_published'] is True
    assert sum(row['secret'] for row in state['ranking']) == 20000


def test_secret_show_preview_is_synthetic(client):
    old = client.get('/sochi/api/public/state').json()
    p = client.get('/sochi/preview/secret')
    assert p.status_code == 200
    assert 'ДЕМО SECRET JACK · НЕ ЭФИР' in p.text
    for file in ('secret-show.js', 'secret-show.css', 'secret-preview.js'):
        assert client.get('/sochi/static/'+file).status_code == 200
    assert client.get('/sochi/api/public/state').json() == old
    assert client.get('/sochi/api/admin/state').status_code == 401
