"""Pure calculations and the strict, organiser-approved seating importer."""
from collections import Counter, defaultdict

EXPECTED_OCCUPANCY = {10: [10, 10, 10], 11: [8, 8, 8, 9],
                      12: [9, 9, 9, 9], 13: [10, 10, 10, 9]}


def green_points(green_stack: int, reentry_chips: int) -> int:
    return green_stack - reentry_chips


def blue_points(green_stack: int, blue_stack: int, addon_chips: int, survivors: int) -> int:
    if not 0 <= survivors <= 3:
        raise ValueError('survivors must be 0–3')
    return blue_stack - green_stack - addon_chips + 5000 * survivors


def red_points(place: int, count: int) -> int:
    if not 1 <= place <= count:
        raise ValueError('invalid RED place')
    return 130_000 - 10_000 * (place - 1)


def validate_seating(document: dict, team_count: int) -> tuple[list[dict], list[dict]]:
    """Use ONLY variants[N].cards; never synthesize or truncate seating."""
    if team_count not in EXPECTED_OCCUPANCY:
        raise ValueError('team_count must be 10, 11, 12 or 13')
    variants = document.get('variants')
    if not isinstance(variants, dict) or str(team_count) not in variants:
        raise ValueError(f'Approved variants["{team_count}"] is missing')
    source = variants[str(team_count)]
    cards = source.get('cards') if isinstance(source, dict) else None
    if not isinstance(cards, list) or len(cards) != team_count * 3:
        raise ValueError('Variant must contain exactly 3 cards per team')
    original_teams = document.get('teams')
    if not isinstance(original_teams, list):
        raise ValueError('JSON must contain teams list')
    teams_by_id = {}
    for i, team in enumerate(original_teams):
        if isinstance(team, str):
            team = {'team_id': i + 1, 'team': team}
        if not isinstance(team, dict):
            raise ValueError('Invalid team definition')
        team_id = int(team.get('team_id', i + 1))
        name = str(team.get('original_name') or team.get('team') or team.get('name') or '').strip()
        if not name or team_id in teams_by_id:
            raise ValueError('Missing or duplicate team name/id')
        teams_by_id[team_id] = {'team_id': team_id, 'original_name': name}
    if not set(range(1, team_count + 1)).issubset(teams_by_id):
        raise ValueError('The approved team definitions are incomplete')
    parsed = []
    by_team = defaultdict(list)
    occupied = set()
    card_ids = set()
    counters = Counter()
    for c in cards:
        if not isinstance(c, dict):
            raise ValueError('Invalid card')
        for key in ('team_id', 'table', 'box', 'card_id'):
            if key not in c:
                raise ValueError('Card is missing ' + key)
        team_id, table, box, card_id = int(c['team_id']), int(c['table']), int(c['box']), str(c['card_id'])
        max_table = 3 if team_count == 10 else 4
        if team_id < 1 or team_id > team_count or not 1 <= table <= max_table or not 1 <= box <= 10:
            raise ValueError('Card references an invalid team/table/box')
        if (table, box) in occupied or card_id in card_ids or not card_id:
            raise ValueError('Duplicate (table, box) or card_id')
        if c.get('team') and str(c['team']).strip() != teams_by_id[team_id]['original_name']:
            raise ValueError('Card team name does not match team_id')
        occupied.add((table, box))
        card_ids.add(card_id)
        counters[table] += 1
        by_team[team_id].append(table)
        parsed.append({'card_id': card_id, 'team_id': team_id, 'table': table, 'box': box})
    for team_id in range(1, team_count + 1):
        tables = by_team[team_id]
        if len(tables) != 3 or len(set(tables)) != 3:
            raise ValueError(f'Team {team_id} must occupy three different tables')
    observed = [counters[t] for t in range(1, len(EXPECTED_OCCUPANCY[team_count]) + 1)]
    if observed != EXPECTED_OCCUPANCY[team_count]:
        raise ValueError(f'Invalid table occupancy {observed}; expected {EXPECTED_OCCUPANCY[team_count]}')
    return [teams_by_id[x] for x in range(1, team_count + 1)], parsed


def published_ranking(team_names: dict[int, str], stages: dict, secrets: list[dict],
                      votes: list[dict], revealed_slots: list[int], votes_published: bool,
                      vote_recipient: str, team_count: int) -> list[dict]:
    """Only receives frozen published stage data, never draft data."""
    secret_awards = Counter()
    for secret in secrets:
        if int(secret['slot']) in revealed_slots and secret.get('confirmed') and secret.get('knockout_team_id'):
            secret_awards[int(secret['knockout_team_id'])] += 10_000
    vote_awards = Counter()
    if votes_published:
        for vote in votes:
            recipient = vote['target_team_id'] if vote_recipient == 'target' else vote['voter_team_id']
            vote_awards[int(recipient)] += 10_000
    ranking = []
    for team_id in sorted(team_names):
        entry = stages.get(str(team_id), {})
        g = entry.get('green') or 0
        b = entry.get('blue') or 0
        r = entry.get('red') or 0
        s = secret_awards[team_id]
        v = vote_awards[team_id]
        ranking.append({'team_id': team_id, 'name': team_names[team_id],
                        'green': g, 'blue': b, 'red': r, 'secret': s, 'votes': v,
                        'total': g + b + r + s + v})
    ranking.sort(key=lambda x: (-x['total'], x['team_id']))
    for idx, entry in enumerate(ranking):
        entry['place'] = idx + 1 if idx == 0 or entry['total'] != ranking[idx - 1]['total'] else ranking[idx - 1]['place']
        entry['tied'] = sum(x['total'] == entry['total'] for x in ranking) > 1
    return ranking
