"""Pure calculations and the strict, organiser-approved seating importer."""
from collections import Counter, defaultdict

# Actual chip awards before RED in the final-table tournament format.
FINAL_TABLE_JACK_CHIPS = 10_000
FINAL_TABLE_VOTE_CHIPS = 20_000
GREEN_BOUNTY_CHIPS = 2_500
BLUE_BOUNTY_CHIPS = 5_000

EXPECTED_OCCUPANCY = {10: [10, 10, 10], 11: [8, 8, 8, 9],
                      12: [9, 9, 9, 9], 13: [10, 10, 10, 9]}


def green_points(green_stack: int, reentry_chips: int, entry_chips: int = 0) -> int:
    """Net GREEN chips, including the initial entry for each participant."""
    return green_stack - reentry_chips - entry_chips


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


def final_table_stacks(chips: dict[int, int], team_count: int) -> dict[str, int]:
    """Proportional physical chips at the final table, to 1,000-chip increments.

    The smallest BLUE NET stack receives 100,000 and the largest 1,000,000.
    Equal raw net stacks are equal at the final table. An exact tie across all
    participants is neutralised at 550,000 each: no arbitrary first/last.
    A 1,000-chip denomination is practical and keeps the endpoints exact.
    """
    if set(chips) != set(range(1, team_count + 1)):
        raise ValueError('Финальный стол: нужны чистые фишки BLUE всех команд')
    if any(type(v) is not int for v in chips.values()):
        raise ValueError('Финальный стол: чистые фишки должны быть целыми')
    lo, hi = min(chips.values()), max(chips.values())
    if hi == lo:
        return {str(tid): 550000 for tid in chips}
    span=hi-lo
    stacks={}
    for tid,raw in chips.items():
        scaled=100000+(900000*(raw-lo)*2+span)//(2*span)
        stacks[str(tid)]=max(100000,min(1000000,((scaled+500)//1000)*1000))
    return stacks


def blue_points_from_policy(chips: dict[int, int], policy: dict, team_count: int) -> dict[str, int]:
    """Map end-of-BLUE NET CHIPS to tournament points without altering chip accounting.

    chips: cumulative GREEN+BLUE net chips for each team.
    chips/scale/places modes preserve the sporting ranking by *net chips*.
    Equal chips get equal sporting places, therefore the same place-points.
    """
    if set(chips) != set(range(1, team_count + 1)):
        raise ValueError('BLUE: нет чистых фишек для всех команд')
    if not isinstance(policy, dict):
        raise ValueError('BLUE: не выбрана система начисления')
    mode = policy.get('mode')
    if mode not in ('chips', 'scale', 'places', 'final_table'):
        raise ValueError('BLUE: неизвестная система начисления')
    if mode == 'final_table':
        return final_table_stacks(chips,team_count)
    percent = policy.get('percent', 100)
    if mode == 'scale':
        if type(percent) is not int or not 1 <= percent <= 100:
            raise ValueError('Коэффициент: целое число 1–100%')
    points = policy.get('place_points', [])
    if mode == 'places':
        if not isinstance(points, list) or len(points) != team_count:
            raise ValueError('Нужны очки для каждого места BLUE')
        if any(type(x) is not int or not 0 <= x <= 10_000_000 for x in points):
            raise ValueError('Очки за место: целые числа от 0 до 10 000 000')
        if any(points[i] > points[i-1] for i in range(1,len(points))):
            raise ValueError('Очки должны убывать или оставаться равными с ухудшением места')
    ranked = sorted(chips, key=lambda tid: (-chips[tid], tid))
    result = {}
    previous = None
    place = 0
    for index, tid in enumerate(ranked):
        raw = chips[tid]
        if previous is None or raw != previous:
            place = index + 1
        if mode == 'chips':
            assigned = raw
        elif mode == 'scale':
            numerator = abs(raw) * percent
            assigned = (numerator + 50) // 100 * (-1 if raw < 0 else 1)
        else:
            assigned = points[place - 1]
        result[str(tid)] = assigned
        previous = raw
    return result


def published_ranking(team_names: dict[int, str], stages: dict, secrets: list[dict],
                      votes: list[dict], revealed_slots: list[int], votes_published: bool,
                      vote_recipient: str, team_count: int,
                      blue_base_points: dict | None = None,
                      final_table_mode: bool = False,
                      team_bounties: dict | None = None) -> list[dict]:
    """Only receives frozen published stage data, never draft data."""
    secret_awards = Counter()
    for secret in secrets:
        if int(secret['slot']) in revealed_slots and secret.get('confirmed') and secret.get('knockout_team_id'):
            secret_awards[int(secret['knockout_team_id'])] += (FINAL_TABLE_JACK_CHIPS if final_table_mode else 10_000)
    vote_awards = Counter()
    if votes_published:
        for vote in votes:
            recipient = vote['target_team_id'] if vote_recipient == 'target' else vote['voter_team_id']
            vote_awards[int(recipient)] += FINAL_TABLE_VOTE_CHIPS if final_table_mode else 10_000
    ranking = []
    for team_id in sorted(team_names):
        entry = stages.get(str(team_id), {})
        g = entry.get('green') or 0
        b = entry.get('blue') or 0
        r = entry.get('red') or 0
        s = secret_awards[team_id]
        v = vote_awards[team_id]
        # BLUE is a final *raw-chip* snapshot. The survival award is not
        # part of the chip stack and must not determine BLUE sporting places.
        survivor_bonus = int(entry.get('survivor_bonus', 0))
        chip_net = entry.get('blue_net_chips', g + b)
        converted = (blue_base_points or {}).get(str(team_id), chip_net)
        bounty = (team_bounties or {}).get(str(team_id), {}) if final_table_mode else {}
        bounty_chips = int(bounty.get('chips', 0))
        award = converted + survivor_bonus + bounty_chips
        result = {'team_id': team_id, 'name': team_names[team_id],
                  'green': g, 'blue': b, 'chip_net': chip_net,
                  'survivor_bonus': survivor_bonus, 'bounty_chips': bounty_chips,
                  'bounty_green': int(bounty.get('green', 0)),
                  'bounty_blue': int(bounty.get('blue', 0)),
                  'base_points': award, 'red': r, 'secret': s, 'votes': v,
                  'total': award + r + s + v}
        if final_table_mode and 'red' in entry:
            # Compatible with snapshots published before red_place was stored:
            # the legacy RED score uniquely encodes the elimination order.
            result['red_place'] = entry.get('red_place') or (
                1 + (130_000 - int(entry['red'])) // 10_000)
        ranking.append(result)
    if final_table_mode and all('red_place' in row for row in ranking):
        places = sorted(row['red_place'] for row in ranking)
        if places != list(range(1, team_count + 1)):
            raise ValueError('RED: итоговые места должны быть уникальными 1..N')
        # The champion is the captain who won the RED table. A higher stack
        # or old 130k.. scoring cannot rescue an eliminated captain.
        ranking.sort(key=lambda row: row['red_place'])
        for row in ranking:
            row['place'] = row['red_place']
            row['tied'] = False
    else:
        ranking.sort(key=lambda x: (-x['total'], x['team_id']))
        for idx, entry in enumerate(ranking):
            entry['place'] = idx + 1 if idx == 0 or entry['total'] != ranking[idx - 1]['total'] else ranking[idx - 1]['place']
            entry['tied'] = sum(x['total'] == entry['total'] for x in ranking) > 1
    return ranking
