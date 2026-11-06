"""RED cinematic publication: stable math, no leak, safe bonus handoff."""
import pytest
from test_show import auth, call, prepare, client


def ready_for_red(client, headers, n):
    prepare(client, headers, n=n)
    assert call(client, 'chips-settings', headers, {'reentry': 30000, 'addon': 50000}).status_code == 200
    assert call(client, 'publish', headers, {'action': 'teams'}).status_code == 200
    greens = [{'team_id': i, 'green_stack': 100000 + 10000 * i, 'reentry_count': 0}
              for i in range(1, n+1)]
    assert call(client, 'stages/bulk', headers, {'phase': 'green', 'teams': greens}).status_code == 200
    assert call(client, 'publish', headers, {'action': 'green', 'show_mode': 'cinematic'}).status_code == 200
    for step in range(1, n+2):
        assert call(client, 'publish', headers, {'action': 'green-show-step', 'step': step}).status_code == 200

    blues = [{'team_id': i, 'blue_stack': 100000 + 10000 * i + (300000 if i == 1 else 0),
              'addon_count': 0, 'survivors': 0} for i in range(1, n+1)]
    assert call(client, 'stages/bulk', headers, {'phase': 'blue', 'teams': blues}).status_code == 200
    assert call(client, 'publish', headers, {'action': 'blue', 'show_mode': 'cinematic'}).status_code == 200
    for step in range(1, n+2):
        assert call(client, 'publish', headers, {'action': 'blue-show-step', 'step': step}).status_code == 200

    red_rows = [{'team_id': i, 'red_place': n - i + 1} for i in range(1, n+1)]
    assert call(client, 'stages/bulk', headers, {'phase': 'red', 'teams': red_rows}).status_code == 200


@pytest.mark.parametrize('n', [10, 11])
def test_red_cinematic_publish_hides_all_unrevealed_scores(client, n):
    h = auth(client)
    ready_for_red(client, h, n)
    response = call(client, 'publish', h, {'action': 'red', 'show_mode': 'cinematic'})
    assert response.status_code == 200, response.text
    pub = client.get('/sochi/api/public/state').json()['state']
    assert pub['scene'] == 'red_show'
    assert pub['published_phases'] == ['green', 'blue', 'red']
    assert pub['red_view'] == {'count': n, 'step': 0, 'max_step': n+1, 'revealed': []}
    assert pub['ranking'] == []
    assert pub['stages'] == {}
    assert pub['recent_changes'] == []
    assert 'ranking' not in pub['red_show']
    assert 'red' not in str(pub['red_view'])
    assert not pub['revealed_secrets'] and not pub['votes_published']

    assert call(client, 'publish', h, {'action': 'red'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'red-show-step', 'step': 3}).status_code == 409
    for action in ('reveal', 'votes', 'blue', 'green'):
        assert call(client, 'publish', h, {'action': action}).status_code == 409
    for scene in ('green', 'blue', 'red', 'secrets', 'votes', 'winner', 'final'):
        assert call(client, 'publish', h, {'action': 'scene', 'scene': scene}).status_code == 409

    for step in range(1, n+2):
        r = call(client, 'publish', h, {'action': 'red-show-step', 'step': step})
        assert r.status_code == 200, r.text
        state = client.get('/sochi/api/public/state').json()['state']
        view = state['red_view']
        assert view['step'] == step
        assert len(view['revealed']) == min(step, n)
        assert 'ranking' not in state['red_show']
        assert 'green_stack_actual' not in str(state)
        if step < n+1:
            assert state['ranking'] == []
            assert state['stages'] == {}
        if step == 1:
            # team 2 has the fewest cumulative points; first reveal is bottom.
            assert view['revealed'][0]['team_id'] == 2
            assert view['revealed'][0]['red_place'] == n-1
            assert view['revealed'][0]['red'] == 130000 - 10000 * (n-2)
        if step == n:
            winner = view['revealed'][-1]
            assert winner['team_id'] == 1
            assert winner['place'] == 1
            assert winner['red_place'] == n
            assert winner['red'] == 130000 - 10000 * (n-1)
            assert winner['total'] == 410000 + winner['red']
            assert winner['blue_place'] == 1
    final = client.get('/sochi/api/public/state').json()['state']
    assert len(final['ranking']) == n
    assert final['red_view']['max_step'] == n+1
    assert call(client, 'publish', h, {'action': 'red-show-step', 'step': n+2}).status_code == 422

    assert call(client, 'publish', h, {'action': 'red-show-step', 'step': n}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['ranking'] == []
    assert call(client, 'publish', h, {'action': 'red-show-step', 'step': n+1}).status_code == 200
    assert call(client, 'publish', h, {'action': 'red-show-start'}).status_code == 200
    again = client.get('/sochi/api/public/state').json()['state']
    assert again['red_view']['revealed'] == []
    assert again['ranking'] == []


def test_red_show_rejects_before_red_and_allows_legacy_publish(client):
    h = auth(client)
    assert call(client, 'publish', h, {'action': 'red-show-start'}).status_code == 409
    ready_for_red(client, h, 10)
    assert call(client, 'publish', h, {'action': 'red'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'red-show-start'}).status_code == 200
    pub = client.get('/sochi/api/public/state').json()['state']
    assert pub['red_view']['revealed'] == []


def test_red_rehearsal_uses_only_synthetic_data(client):
    before = client.get('/sochi/api/public/state').json()
    page = client.get('/sochi/preview/red')
    assert page.status_code == 200
    assert 'ДЕМО RED' in page.text
    for file in ('red-show.css', 'red-show.js', 'red-preview.js',
                 'rank-mascots.js', 'jack-sword-motion.js'):
        assert client.get('/sochi/static/' + file).status_code == 200
    assert client.get('/sochi/api/public/state').json() == before
    assert client.get('/sochi/api/admin/state').status_code == 401
