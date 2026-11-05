"""GREEN show staging and public spoiler protection without changing the running projector."""
from test_show import auth, call, prepare, client


def test_green_rehearsal_requires_login_and_is_read_only(client):
    assert client.get('/sochi/preview/green').status_code == 401
    headers = auth(client)
    before = client.get('/sochi/api/admin/state').json()['publication_version']
    response = client.get('/sochi/preview/green')
    assert response.status_code == 200
    assert 'ДЕМО-ПРОСМОТР' in response.text
    assert 'green-show.js' in response.text
    for path in ('green-show.css', 'green-show.js', 'green-preview.js'):
        r = client.get('/sochi/static/' + path)
        assert r.status_code == 200 and r.content
    assert client.get('/sochi/api/admin/state').json()['publication_version'] == before


def test_green_show_sequential_reveal_never_leaks_unopened_ranking(client):
    h = auth(client)
    prepare(client, h, n=10)
    assert call(client, 'chips-settings', h, {'reentry': 30000}).status_code == 200
    rows = [{'team_id': i, 'green_stack': 100000 + i * 10000, 'reentry_count': 0}
            for i in range(1, 11)]
    assert call(client, 'stages/bulk', h, {'phase': 'green', 'teams': rows}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green-show-start'}).status_code == 200
    initial = client.get('/sochi/api/public/state').json()['state']
    assert initial['scene'] == 'green_show'
    assert initial['green_view']['step'] == 0
    assert initial['green_view']['count'] == 10
    assert initial['green_view']['revealed'] == []
    assert initial['ranking'] == []
    assert initial['stages'] == {}
    assert 'ranking' not in initial['green_show']
    assert '"green":200000' not in client.get('/sochi/api/public/state').text
    assert call(client, 'publish', h, {'action': 'green-show-step', 'step': 3}).status_code == 409
    assert call(client, 'publish', h, {'action': 'blue'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'green'}).status_code == 409
    assert call(client, 'publish', h, {'action': 'scene', 'scene': 'green'}).status_code == 409

    for step in range(1, 13):
        r = call(client, 'publish', h, {'action': 'green-show-step', 'step': step})
        assert r.status_code == 200, r.text
        pub = client.get('/sochi/api/public/state').json()['state']
        assert pub['scene'] == 'green_show'
        view = pub['green_view']
        assert view['step'] == step
        assert len(view['revealed']) == min(step, 10)
        # Secrets are never part of this count-only GREEN frame.
        assert 'ranking' not in pub['green_show']
        if step < 12:
            assert pub['ranking'] == []
            assert pub['stages'] == {}
        if step == 1:
            assert view['revealed'][0]['team_id'] == 1
            assert view['revealed'][0]['green'] == 110000
            assert '210000' not in str(view)
        if step == 10:
            assert view['revealed'][-1]['team_id'] == 10

    assert call(client, 'publish', h, {'action': 'green-show-step', 'step': 13}).status_code == 422
    assert call(client, 'publish', h, {'action': 'green-show-step', 'step': 11}).status_code == 200
    assert len(client.get('/sochi/api/public/state').json()['state']['green_view']['revealed']) == 10
    assert call(client, 'publish', h, {'action': 'green-show-step', 'step': 12}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green-show-start'}).status_code == 200
    reset = client.get('/sochi/api/public/state').json()['state']
    assert reset['green_view']['revealed'] == []


def test_green_show_cannot_start_before_green_or_after_blue(client):
    h = auth(client)
    prepare(client, h, 10)
    assert call(client, 'publish', h, {'action': 'green-show-start'}).status_code == 409
    assert call(client, 'chips-settings', h, {'reentry': 30000, 'addon': 50000}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200
    green = [{'team_id': i, 'green_stack': 150000, 'reentry_count': 0}
             for i in range(1, 11)]
    blue = [{'team_id': i, 'blue_stack': 170000, 'addon_count': 0, 'survivors': 1}
            for i in range(1, 11)]
    assert call(client, 'stages/bulk', h, {'phase': 'green', 'teams': green}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green'}).status_code == 200
    assert call(client, 'stages/bulk', h, {'phase': 'blue', 'teams': blue}).status_code == 200
    assert call(client, 'publish', h, {'action': 'blue'}).status_code == 200
    assert call(client, 'publish', h, {'action': 'green-show-start'}).status_code == 409


def test_green_cinematic_publication_is_atomic_and_private(client):
    h = auth(client)
    prepare(client, h, 10)
    assert call(client, 'chips-settings', h, {'reentry': 30000}).status_code == 200
    rows = [{'team_id': i, 'green_stack': 100000 + 10000*i,
             'reentry_count': 1 if i == 1 else 0} for i in range(1, 11)]
    assert call(client, 'stages/bulk', h, {'phase': 'green', 'teams': rows}).status_code == 200
    assert call(client, 'publish', h, {'action': 'teams'}).status_code == 200

    # The organizer's GREEN publish button submits 'show_mode: cinematic'.
    # One transaction freezes GREEN and opens an intro with no public scores.
    response = call(client, 'publish', h, {'action': 'green', 'show_mode': 'cinematic'})
    assert response.status_code == 200, response.text
    p = client.get('/sochi/api/public/state').json()['state']
    assert p['scene'] == 'green_show'
    assert p['published_phases'] == ['green']
    assert p['green_view']['revealed'] == []
    assert p['ranking'] == []
    assert p['stages'] == {}
    assert 'green_stack_actual' not in str(p)
    # No explicit GreenShow 'start' action is necessary to begin revealing.
    assert call(client, 'publish', h, {'action': 'green-show-step', 'step': 1}).status_code == 200
    v = client.get('/sochi/api/public/state').json()['state']['green_view']
    assert len(v['revealed']) == 1
    assert v['revealed'][0]['green'] == 80000
