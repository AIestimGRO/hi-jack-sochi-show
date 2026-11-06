"""Captain vote show: locked ballots, per-step privacy, single +10k, replay, two modes."""
import json
import pytest

from test_show import auth, call, client
from test_secret_show import ready


def completed_secrets(client, headers, n):
    ready(client, headers, n)
    assert call(client, 'publish', headers, {'action': 'secret-show-start'}).status_code == 200
    for slot in (1, 2, 3):
        assert call(client, 'publish', headers, {'action': 'reveal', 'slot': slot}).status_code == 200
    assert call(client, 'publish', headers, {'action': 'secret-show-step', 'step': 4}).status_code == 200
    return client.get('/sochi/api/public/state').json()['state']['ranking']


@pytest.mark.parametrize('count', [10, 11])
@pytest.mark.parametrize('mode', ['target', 'voter'])
def test_vote_show_prefix_is_private_replay_is_idempotent(client, count, mode):
    h = auth(client)
    base = completed_secrets(client, h, count)
    by_team = {r['team_id']: r for r in base}
    assert all(r['votes'] == 0 for r in base)
    assert call(client, 'vote-mode', h, {'mode': mode}).status_code == 200
    # The same recipients receive votes as in the legacy voting rules.
    for voter in range(1, count + 1):
        target = 2 if voter != 2 else 1
        assert call(client, 'vote', h, {'voter_team_id': voter,
                                       'target_team_id': target}).status_code == 200

    assert call(client, 'publish', h, {'action': 'vote-show-step', 'step': 1}).status_code == 409
    assert call(client, 'publish', h, {'action': 'vote-show-start'}).status_code == 409
    publish = call(client, 'publish', h, {'action': 'votes', 'show_mode': 'cinematic'})
    assert publish.status_code == 200, publish.text

    public = client.get('/sochi/api/public/state').json()['state']
    assert public['scene'] == 'vote_show'
    assert public['vote_view']['step'] == 0
    assert public['vote_view']['revealed'] == []
    assert public['vote_view']['current'] is None
    assert len(public['vote_view']['ranking']) == count
    assert public['vote_show'] == {'step': 0, 'count': count, 'max_step': count + 1}
    assert 'entries' not in json.dumps(public['vote_show'])
    assert 'base_ranking' not in json.dumps(public)
    assert public['published_votes'] == []
    assert public['votes_published'] is False
    assert all(r['votes'] == 0 for r in public['ranking'])
    assert public['ranking'] == public['vote_view']['ranking'] or all(
        r['votes'] == 0 for r in public['ranking'])
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'final'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'winner'}).status_code == 409

    for step in range(1, count + 2):
        r = call(client, 'publish', h, {'action': 'vote-show-step', 'step': step})
        assert r.status_code == 200, r.text
        state = client.get('/sochi/api/public/state').json()['state']
        view = state['vote_view']
        assert view['step'] == step
        assert len(view['revealed']) == min(step, count)
        assert len(state['published_votes']) == min(step, count)
        assert state['vote_show'] == {'step': step, 'count': count, 'max_step': count + 1}
        assert sum(row['votes'] for row in state['ranking']) == 10000 * min(step, count)
        assert [row['voter_team_id'] for row in view['revealed']] == list(range(1, min(step, count)+1))
        if step < count+1:
            assert state['votes_published'] is False
        if step == 1:
            assert view['current']['voter_team_id'] == 1
            assert view['current']['target_team_id'] == 2
            receiver = 2 if mode == 'target' else 1
            assert view['current']['receiver_team_id'] == receiver
            assert next(r for r in state['ranking'] if r['team_id'] == receiver)['votes'] == 10000
            assert all(v['voter_team_id'] == 1 for v in state['published_votes'])
            assert call(client, 'publish', h, {'action': 'vote-show-step', 'step': 3}).status_code == 409

    final = client.get('/sochi/api/public/state').json()['state']
    assert final['vote_view']['summary'] is True
    assert final['votes_published'] is True
    assert sum(row['votes'] for row in final['ranking']) == count * 10000
    assert sum(row['total'] for row in final['ranking']) == (
        sum(row['total'] for row in base) + count*10000)
    if mode == 'target':
        assert next(r for r in final['ranking'] if r['team_id'] == 2)['votes'] == (count-1)*10000
    else:
        assert all(r['votes'] == 10000 for r in final['ranking'])
    assert call(client, 'vote-mode', h, {'mode': 'target' if mode=='voter' else 'voter'}).status_code == 409

    # Replay shows no scores before their corresponding vote is revealed.
    assert call(client, 'publish', h, {'action': 'vote-show-start'}).status_code == 200
    replay = client.get('/sochi/api/public/state').json()['state']
    assert replay['vote_view']['revealed'] == []
    assert replay['votes_published'] is False
    assert all(r['votes'] == 0 for r in replay['ranking'])
    for step in range(1, count + 2):
        assert call(client, 'publish', h, {'action': 'vote-show-step', 'step': step}).status_code == 200
    again = client.get('/sochi/api/public/state').json()['state']
    assert again['ranking'] == final['ranking']
    assert call(client, 'publish', h, {'action': 'vote-show-step', 'step': count+2}).status_code == 422
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'final'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'vote-show-start'}).status_code == 409


def test_vote_show_legacy_votes_remain_supported(client):
    h = auth(client)
    completed_secrets(client, h, 10)
    for i in range(1,11):
        assert call(client, 'vote', h, {'voter_team_id':i,
                                       'target_team_id':2 if i!=2 else 1}).status_code == 200
    assert call(client, 'publish', h, {'action': 'votes'}).status_code == 200
    pub = client.get('/sochi/api/public/state').json()['state']
    assert pub['scene'] == 'votes'
    assert 'vote_show' not in pub
    assert pub['votes_published'] is True
    assert sum(r['votes'] for r in pub['ranking']) == 100000


def test_vote_show_demo_is_fictional_and_read_only(client):
    prior = client.get('/sochi/api/public/state').json()
    page = client.get('/sochi/preview/vote')
    assert page.status_code == 200
    assert 'ДЕМО ГОЛОСОВ КАПИТАНОВ · НЕ ЭФИР' in page.text
    for asset in ('vote-show.js', 'vote-show.css', 'vote-preview.js'):
        response=client.get('/sochi/static/'+asset)
        assert response.status_code == 200 and response.content
    assert client.get('/sochi/api/public/state').json() == prior
    assert client.get('/sochi/api/admin/state').status_code == 401


def test_vote_show_cannot_start_before_captains_finish(client):
    h=auth(client)
    ready(client,h,10)
    for i in range(1,11):
        assert call(client,'vote',h,{'voter_team_id':i,'target_team_id':2 if i!=2 else 1}).status_code == 200
    assert call(client,'publish',h,{'action':'secret-show-start'}).status_code==200
    for slot in (1,2,3):
        assert call(client,'publish',h,{'action':'reveal','slot':slot}).status_code==200
    result=call(client,'publish',h,{'action':'votes','show_mode':'cinematic'})
    assert result.status_code==409
    assert call(client,'publish',h,{'action':'secret-show-step','step':4}).status_code==200
    result=call(client,'publish',h,{'action':'votes','show_mode':'cinematic'})
    assert result.status_code==200
