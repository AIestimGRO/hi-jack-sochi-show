"""Captain selection and projector publication must be one atomic operation."""
from test_show import auth, call, prepare, client


def fixture_captains(client, headers):
    state = prepare(client, headers, 10, players=True)
    selected = {}
    for seat in state['seats']:
        selected.setdefault(seat['team_id'], seat['player_id'])
    assert len(selected) == 10
    return selected


def test_publish_captains_saves_all_dropdown_choices_atomically(client):
    h = auth(client)
    picks = fixture_captains(client, h)
    assert all(t['captain_player_id'] is None
               for t in client.get('/sochi/api/admin/state').json()['teams'])
    assignments = [{'team_id':team, 'captain_player_id':pid}
                   for team,pid in sorted(picks.items())]
    result = call(client, 'publish', h, {
        'action':'captains', 'captain_assignments':assignments
    })
    assert result.status_code == 200, result.text
    state = client.get('/sochi/api/admin/state').json()
    assert state['published']['scene'] == 'captains'
    assert {t['team_id']:t['captain_player_id'] for t in state['teams']} == picks
    assert {t['team_id']:t['player_id']
            for t in state['published']['captains']} == picks
    assert {r['team_id']:r['player_id']
            for r in client.get('/sochi/api/public/state').json()['state']['captains']} == picks


def test_publish_invalid_captain_selection_keeps_all_previous_assignments(client):
    h = auth(client)
    picks = fixture_captains(client, h)
    assignments = [{'team_id':team, 'captain_player_id':pid}
                   for team,pid in sorted(picks.items())]
    assignments[-1]['captain_player_id'] = picks[1]
    response = call(client, 'publish', h, {
        'action':'captains', 'captain_assignments':assignments
    })
    assert response.status_code == 422
    state = client.get('/sochi/api/admin/state').json()
    assert all(t['captain_player_id'] is None for t in state['teams'])
    assert not state['published']['captains']
    assert state['published']['scene'] == 'intro'


def test_publish_captains_rejects_incomplete_or_duplicate_assignment_list(client):
    h = auth(client)
    picks = fixture_captains(client, h)
    assignments = [{'team_id':team,'captain_player_id':pid}
                   for team,pid in sorted(picks.items())]
    for bad in (assignments[:-1], assignments[:-1] + [assignments[0]]):
        response = call(client, 'publish', h, {
            'action':'captains', 'captain_assignments':bad
        })
        assert response.status_code == 422
    state = client.get('/sochi/api/admin/state').json()
    assert all(t['captain_player_id'] is None for t in state['teams'])


def test_can_republish_captains_during_green_but_not_after_red(client):
    h = auth(client)
    picks = fixture_captains(client, h)
    first = [{'team_id':tid, 'captain_player_id':pid}
             for tid,pid in sorted(picks.items())]
    assert call(client, 'publish', h, {'action':'teams'}).status_code == 200
    assert call(client, 'publish', h, {
        'action':'captains', 'captain_assignments':first
    }).status_code == 200
    assert call(client, 'chips-settings', h,
                {'entry':0, 'reentry':30000}).status_code == 200
    rows = [{'team_id':tid, 'green_stack':300000, 'reentry_count':0}
            for tid in sorted(picks)]
    assert call(client, 'stages/bulk', h, {'phase':'green','teams':rows}).status_code == 200
    assert call(client, 'publish', h, {'action':'green'}).status_code == 200
    seats=client.get('/sochi/api/admin/state').json()['seats']
    alternative={}
    for seat in seats:
        if seat['team_id'] in picks and seat['player_id'] != picks[seat['team_id']]:
            alternative.setdefault(seat['team_id'],seat['player_id'])
    second = [{'team_id':tid, 'captain_player_id':alternative[tid]}
              for tid in sorted(picks)]
    response=call(client, 'publish', h, {
        'action':'captains', 'captain_assignments':second
    })
    assert response.status_code == 200, response.text
    current=client.get('/sochi/api/admin/state').json()
    assert {row['team_id']:row['captain_player_id'] for row in current['teams']} == alternative
    assert {row['team_id']:row['player_id']
            for row in current['published']['captains']} == alternative


def test_admin_ui_sends_selected_captains_with_publish():
    from pathlib import Path
    code = (Path(__file__).resolve().parents[1] /
            'sochi_show/static/admin.js').read_text('utf-8')
    assert 'captain_assignments=state.teams.map' in code
    assert "publish({action:'captains',captain_assignments}" in code
