"""BLUE cinematic director: no spoilers, correct GREEN+BLUE math and safe replay."""
import pytest
from test_show import auth, call, prepare, client


def setup_stages(client, h, n):
    prepare(client, h, n=n)
    assert call(client, 'chips-settings', h, {'reentry': 30000, 'addon': 50000}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    green_rows = [{'team_id': i, 'green_stack': 100000 + 10000 * i, 'reentry_count': 0}
                  for i in range(1, n + 1)]
    assert call(client, 'stages/bulk', h, {'phase': 'green', 'teams': green_rows}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green', 'show_mode': 'cinematic'}).status_code == 200
    for step in range(1, n + 2):
        r = call(client, 'publish', h, {'action': 'green-show-step', 'step': step})
        assert r.status_code == 200, r.text
    blue_rows = [{'team_id': i,
                  'blue_stack': 100000 + 10000 * i + (300000 if i == 1 else 0),
                  'addon_count': 0, 'survivors': 0}
                 for i in range(1, n + 1)]
    assert call(client, 'stages/bulk', h, {'phase': 'blue', 'teams': blue_rows}).status_code == 200


@pytest.mark.parametrize('n', [10, 11])
def test_blue_publish_is_atomic_and_does_not_spoil_results(client, n):
    h = auth(client)
    setup_stages(client, h, n)
    assert call(client, 'publish', h, {'action': 'blue', 'show_mode': 'cinematic'}).status_code == 200
    pub = client.get('/sochi/api/public/state').json()['state']
    assert pub['scene'] == 'blue_show'
    assert pub['published_phases'] == ['green', 'blue']
    assert pub['blue_view'] == {'count': n, 'step': 0, 'max_step': n + 1, 'revealed': []}
    assert pub['ranking'] == [] and pub['stages'] == {}
    assert 'ranking' not in pub['blue_show']
    assert '300000' not in str(pub['blue_view'])
    assert call(client, 'publish', h, {'action': 'blue-show-step', 'step': 2}).status_code == 409
    assert call(client, 'publish', h, {'action': 'blue'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'red'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'blue'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'final'}).status_code == 409

    for step in range(1, n + 2):
        response = call(client, 'publish', h, {'action': 'blue-show-step', 'step': step})
        assert response.status_code == 200, response.text
        visible = client.get('/sochi/api/public/state').json()['state']
        rows = visible['blue_view']['revealed']
        assert visible['blue_view']['step'] == step
        assert len(rows) == min(step, n)
        assert 'ranking' not in visible['blue_show']
        assert 'blue_stack' not in str(visible)
        if step < n + 1:
            assert visible['ranking'] == []
            assert visible['stages'] == {}
        if step == 1:
            # Lowest cumulative team is team 2 after team 1 leaps from last to first.
            assert rows[0]['team_id'] == 2
            assert rows[0]['move'] == -1
        if step == n:
            winner = rows[-1]
            assert winner['team_id'] == 1
            assert winner['green_place'] == n
            assert winner['place'] == 1
            assert winner['move'] == n - 1
            assert winner['blue'] == 300000
            assert winner['total'] == 410000
    finished = client.get('/sochi/api/public/state').json()['state']
    assert finished['blue_view']['max_step'] == n + 1
    assert finished['blue_view']['revealed'][-1]['place'] == 1
    assert finished['ranking'] == []  # no point leaderboard before protected BLUE decision
    assert call(client, 'publish', h, {'action': 'blue-show-step', 'step': n + 2}).status_code == 422
    assert call(client, 'publish', h, {'action': 'blue-show-step', 'step': n}).status_code == 200
    assert client.get('/sochi/api/public/state').json()['state']['ranking'] == []
    assert call(client, 'publish', h, {'action': 'blue-show-start'}).status_code == 200
    again = client.get('/sochi/api/public/state').json()['state']
    assert again['blue_view']['revealed'] == []


def test_blue_preview_is_public_and_no_database_changes(client):
    before = client.get('/sochi/api/public/state').json()
    preview = client.get('/sochi/preview/blue')
    assert preview.status_code == 200
    assert 'ДЕМО BLUE' in preview.text
    for path in ('blue-show.js', 'blue-show.css', 'blue-preview.js',
                 'rank-mascots.js', 'jack-sword-motion.js'):
        assert client.get('/sochi/static/' + path).status_code == 200
    assert client.get('/sochi/api/public/state').json() == before
    assert client.get('/sochi/api/admin/state').status_code == 401


def test_blue_cannot_start_before_publish_or_after_red(client):
    h = auth(client)
    prepare(client, h, n=10)
    assert call(client, 'publish', h, {'action': 'blue-show-start'}).status_code == 409
    assert call(client, 'chips-settings', h, {'reentry': 30000, 'addon': 50000}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    greens = [{'team_id': i, 'green_stack': 100000, 'reentry_count': 0}
              for i in range(1, 11)]
    blues = [{'team_id': i, 'blue_stack': 110000, 'addon_count': 0, 'survivors': 0}
             for i in range(1, 11)]
    assert call(client, 'stages/bulk', h, {'phase': 'green', 'teams': greens}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green'}).status_code == 200
    assert call(client, 'stages/bulk', h, {'phase': 'blue', 'teams': blues}).status_code == 200
    assert call(client, 'publish', h, {'action': 'blue'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'blue-show-start'}).status_code == 200
    for step in range(1, 12):
        assert call(client, 'publish', h, {'action': 'blue-show-step', 'step': step}).status_code == 200
    reds = [{'team_id': i, 'red_place': i} for i in range(1, 11)]
    assert call(client, 'stages/bulk', h, {'phase': 'red', 'teams': reds}).status_code == 200
    assert call(client, 'publish', h, {'action': 'red'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'blue-show-start'}).status_code == 409
