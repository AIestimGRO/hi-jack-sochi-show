"""Fallback for Wanbo projector browsers that cannot execute modern JS."""
from html import unescape

from sochi_show.legacy_screen import render_legacy_screen
from test_show import client, auth, call, prepare


def test_projector_fallback_requires_no_javascript_and_never_caches(client):
    html = client.get('/sochi/legacy')
    assert html.status_code == 200
    assert 'no-store' in html.headers['cache-control']
    assert '<meta http-equiv="refresh" content="5">' in html.text
    assert '<script' not in html.text.lower()
    assert 'РЕЗУЛЬТАТЫ ПОКА СКРЫТЫ' in html.text
    main = client.get('/sochi/screen').text
    assert 'window.__sochiPainted' in main
    assert '/sochi/legacy' in main
    assert client.get('/sochi/static/screen.js').status_code == 200


def test_projector_fallback_respects_private_unpublished_scores(client):
    h = auth(client)
    prepare(client, h, 10)
    assert call(client, 'stage', h, {'team_id':1, 'green_stack':123456,
                                     'reentry_count':0, 'blue_stack':444444,
                                     'addon_count':0, 'survivors':0,
                                     'red_place':1}).status_code == 200
    response = client.get('/sochi/legacy')
    assert response.status_code == 200
    assert '123456' not in response.text
    assert '444444' not in response.text


def test_projector_fallback_escapes_player_names_and_hides_unrevealed_final():
    example = {'scene':'teams','team_count':1, 'teams':{'1':'<script>alert(1)</script>'}}
    result = render_legacy_screen(example)
    assert '<script>alert(1)</script>' not in result
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in result
    hidden = render_legacy_screen({'scene':'final_show',
        'team_count':10, 'final_view':{'step':0, 'revealed':[], 'board':[], 'champion':None}})
    assert 'РЕЗУЛЬТАТЫ ПОКА СКРЫТЫ' in hidden
