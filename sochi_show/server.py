"""Standalone FastAPI app. Does not import or access JACKSIDE/timer code or databases."""
import asyncio
import copy
import io
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.middleware.sessions import SessionMiddleware

from .core import blue_points, green_points, published_ranking, red_points, validate_seating
from .corrections import correction, rebuild as rebuild_corrected, score_delta

HERE = Path(__file__).resolve().parent
SCENES = {'intro', 'teams', 'green', 'blue', 'captains', 'red', 'secrets', 'votes', 'final', 'winner', 'pause'}
PHASES = ('green', 'blue', 'red')
COLUMNS = ('green_stack', 'reentry_count', 'blue_stack', 'addon_count', 'survivors', 'red_place')
CHIP_LIMIT = 1_000_000_000
COUNT_LIMIT = 1000


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def empty_public():
    return {'scene': 'intro', 'team_count': 0, 'teams': {}, 'roster': {}, 'stages': {},
            'published_phases': [], 'revealed_slots': [], 'revealed_secrets': [],
            'votes_published': False, 'published_votes': [], 'vote_mode': 'target',
            'captains': [], 'ranking': [], 'recent_changes': [], 'winner_decision': None}


def app_factory(db_path: str | None = None, media_path: str | None = None,
                admin_password: str | None = None, session_secret: str | None = None,
                secure_cookie: bool | None = None) -> FastAPI:
    db = Path(db_path or os.environ.get('SOCHI_DATABASE', './data/sochi.sqlite3')).resolve()
    media = Path(media_path or os.environ.get('SOCHI_MEDIA_DIR', './data/media')).resolve()
    password = admin_password if admin_password is not None else os.environ.get('SOCHI_ADMIN_PASSWORD', '')
    session_key = session_secret or os.environ.get('SOCHI_SESSION_SECRET', '')
    if len(session_key) < 32:
        # Misconfigured service should fail closed, rather than use known credentials.
        raise RuntimeError('SOCHI_SESSION_SECRET must be at least 32 characters')
    # A short, operator-friendly 4-digit PIN is allowed for this live event.
    # Longer passwords remain supported for existing deployments and tests.
    if not (re.fullmatch(r'[0-9]{4}', password) or len(password) >= 16):
        raise RuntimeError('SOCHI_ADMIN_PASSWORD must be a 4-digit PIN or at least 16 characters')
    secure = secure_cookie if secure_cookie is not None else os.environ.get('SOCHI_SECURE_COOKIE', 'true').lower() == 'true'
    db.parent.mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title='HI, JACK — HI, SOCHI SHOW', docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=session_key,
                       session_cookie='sochi_session', same_site='strict', https_only=secure,
                       max_age=12 * 3600)
    app.mount('/sochi/static', StaticFiles(directory=HERE / 'static'), name='sochi_static')
    login_attempts: dict[str, list[float]] = {}
    # Shared failure budget prevents distributed PIN guessing from many IPs.
    # Failed attempts only; never log the supplied secret.
    global_login_failures: list[float] = []
    correction_failures: dict[str, list[float]] = {}
    global_correction_failures: list[float] = []

    @contextmanager
    def connection(write=False):
        c = sqlite3.connect(str(db), timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=10000')
        try:
            if write:
                c.execute('BEGIN IMMEDIATE')
            yield c
            if write:
                c.commit()
        except Exception:
            if write:
                c.rollback()
            raise
        finally:
            c.close()

    with connection() as c:
        c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS teams (team_id INTEGER PRIMARY KEY,original_name TEXT NOT NULL,display_name TEXT NOT NULL,captain_player_id INTEGER);
            CREATE TABLE IF NOT EXISTS seats (card_id TEXT PRIMARY KEY,team_id INTEGER NOT NULL,table_no INTEGER NOT NULL,box_no INTEGER NOT NULL,player_id INTEGER UNIQUE,UNIQUE(table_no,box_no));
            CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,photo_path TEXT);
            CREATE TABLE IF NOT EXISTS stages (team_id INTEGER PRIMARY KEY,green_stack INTEGER,reentry_chips INTEGER,reentry_count INTEGER,blue_stack INTEGER,addon_chips INTEGER,addon_count INTEGER,survivors INTEGER,red_place INTEGER);
            CREATE TABLE IF NOT EXISTS secrets (slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 3),player_id INTEGER NOT NULL UNIQUE,knockout_team_id INTEGER,knockout_player_id INTEGER,confirmed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS votes (voter_team_id INTEGER PRIMARY KEY,target_team_id INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS publication (id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,action TEXT NOT NULL,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS correction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                field_name TEXT NOT NULL,
                previous_value TEXT,
                updated_value TEXT,
                previous_state TEXT NOT NULL,
                updated_state TEXT NOT NULL,
                publication_version INTEGER NOT NULL
            );
        ''')
        # Non-destructive migration of the existing independent SOCHI database.
        if 'addon_count' not in {row[1] for row in c.execute('PRAGMA table_info(stages)')}:
            c.execute('ALTER TABLE stages ADD COLUMN addon_count INTEGER')
        c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)', ('team_count', '0'))
        c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)', ('vote_mode', 'target'))
        c.execute('INSERT OR IGNORE INTO publication(id,version,payload) VALUES (1,0,?)', (json.dumps(empty_public()),))
        c.commit()

    def rowdict(row):
        return dict(row) if row else None

    def setting(c, key):
        r = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return r['value'] if r else None

    def team_count(c):
        return int(setting(c, 'team_count') or 0)

    def chip_setting(c, kind):
        raw = setting(c, f'{kind}_chips_per_entry')
        return int(raw) if raw is not None else None

    def require_chip_setting(c, kind):
        value = chip_setting(c, kind)
        if value is None:
            raise HTTPException(409, f'Сначала укажите фишки за одно {kind} в настройках турнира')
        return value

    def get_pub(c):
        row = c.execute('SELECT version,payload FROM publication WHERE id=1').fetchone()
        payload = json.loads(row['payload'])
        # Compatibility: older GREEN SHOW versions had an extra duplicate leader
        # step (N+2). Treat saved N+2 as the new final board step (N+1).
        show = payload.get('green_show')
        if show:
            show['step'] = min(show['step'], len(show['ranking']) + 1)
        blue_show = payload.get('blue_show')
        if blue_show:
            blue_show['step'] = min(blue_show['step'], len(blue_show['ranking']) + 1)
        red_show = payload.get('red_show')
        if red_show:
            red_show['step'] = min(red_show['step'], len(red_show['ranking']) + 1)
        secret_show = payload.get('secret_show')
        if secret_show:
            available = len(payload.get('revealed_secrets', []))
            secret_show['step'] = min(max(0, secret_show['step']),
                                       available + (1 if available == 3 else 0))
        vote_show = payload.get('vote_show')
        if vote_show:
            vote_show['step'] = min(max(0, vote_show['step']), len(vote_show['entries']) + 1)
        final_show = payload.get('final_show')
        if final_show:
            final_show['step'] = min(max(0, final_show['step']), 5)
        return row['version'], payload

    def audit(c, action, data):
        c.execute('INSERT INTO audit(created_at,action,data) VALUES (?,?,?)',
                  (stamp(), action, json.dumps(data, ensure_ascii=False)))

    def save_public(c, state, action='publication'):
        previous_version, previous_state = get_pub(c)
        old_places = {r['team_id']: r['place'] for r in previous_state.get('ranking', [])}
        state['ranking'] = published_ranking(
            {int(k): v for k, v in state['teams'].items()}, state['stages'],
            state['revealed_secrets'], state['published_votes'], state['revealed_slots'],
            state['votes_published'], state['vote_mode'], state['team_count'])
        # A fully reset seating (or a paused tournament with no published stages)
        # must not invent a leaderboard of all-zero tied scores.
        if state.get('scene') == 'pause' and not state['published_phases'] and not state['revealed_slots'] and not state['votes_published']:
            state['ranking'] = []
        state['recent_changes'] = [
            {'team_id': e['team_id'], 'from': old_places[e['team_id']], 'to': e['place']}
            for e in state['ranking'] if e['team_id'] in old_places and old_places[e['team_id']] != e['place']
        ]
        c.execute('UPDATE publication SET version=?,payload=? WHERE id=1',
                  (previous_version + 1, json.dumps(state, ensure_ascii=False)))
        audit(c, action, {'version': previous_version + 1, 'scene': state['scene']})
        return previous_version + 1

    def green_snapshot(p):
        """Capture the stage-only ranking, independent of bonus and later stages."""
        ranked = []
        for team_id, name in p['teams'].items():
            stage = p['stages'].get(team_id, {})
            if 'green' not in stage:
                raise HTTPException(409, 'Отсутствуют опубликованные очки GREEN')
            ranked.append({'team_id': int(team_id), 'name': name, 'green': stage['green']})
        ranked.sort(key=lambda x: (-x['green'], x['team_id']))
        for idx, row in enumerate(ranked):
            row['place'] = idx + 1 if idx == 0 or row['green'] != ranked[idx - 1]['green'] else ranked[idx - 1]['place']
        return {'ranking': ranked, 'step': 0}

    def blue_snapshot(p):
        """Freeze BLUE cumulative ranking and movement from GREEN, without later bonuses."""
        if 'green' not in p['published_phases'] or 'blue' not in p['published_phases']:
            raise HTTPException(409, 'BLUE SHOW доступен только после публикации GREEN и BLUE')
        green_ranked = p.get('green_show', {}).get('ranking') if p.get('green_show') else green_snapshot(p)['ranking']
        green_places = {int(row['team_id']): row['place'] for row in green_ranked}
        ranked = []
        for team_id, name in p['teams'].items():
            stage = p['stages'].get(team_id, {})
            if 'green' not in stage or 'blue' not in stage:
                raise HTTPException(409, 'Нет опубликованных GREEN / BLUE очков для всех команд')
            green = stage['green']
            blue = stage['blue']
            ranked.append({'team_id': int(team_id), 'name': name,
                           'green': green, 'blue': blue, 'total': green + blue,
                           'green_place': green_places[int(team_id)]})
        ranked.sort(key=lambda row: (-row['total'], row['team_id']))
        for index, row in enumerate(ranked):
            row['place'] = (ranked[index - 1]['place']
                            if index and row['total'] == ranked[index - 1]['total']
                            else index + 1)
            # Positive change means climbing from a worse GREEN position.
            row['move'] = row['green_place'] - row['place']
        return {'ranking': ranked, 'step': 0}

    def red_snapshot(p):
        """Cumulative GREEN+BLUE+RED, but never secretly include Jack or votes."""
        if not all(phase in p['published_phases'] for phase in PHASES):
            raise HTTPException(409, 'RED SHOW доступен после GREEN, BLUE и RED')
        blues = p.get('blue_show')
        previous = blues['ranking'] if blues else blue_snapshot(p)['ranking']
        blue_places = {int(r['team_id']): r['place'] for r in previous}
        ranked = []
        for team_id, name in p['teams'].items():
            stage = p['stages'].get(team_id, {})
            if any(stage.get(phase) is None for phase in PHASES):
                raise HTTPException(409, 'Для RED нужны опубликованные очки всех трёх этапов')
            green, blue, red = (stage[k] for k in PHASES)
            ranked.append({'team_id': int(team_id), 'name': name,
                           'green': green, 'blue': blue, 'red': red,
                           'red_place': 1 + (130000 - red) // 10000,
                           'total': green + blue + red,
                           'blue_place': blue_places[int(team_id)]})
        ranked.sort(key=lambda row: (-row['total'], row['team_id']))
        for index, row in enumerate(ranked):
            row['place'] = (ranked[index - 1]['place']
                            if index and row['total'] == ranked[index - 1]['total']
                            else index + 1)
            row['move'] = row['blue_place'] - row['place']
        return {'ranking': ranked, 'step': 0}

    def vote_snapshot(p, votes):
        """Freeze a captain ballot and the last public, pre-vote table once.

        Real ranking continues to use published_ranking. During a reveal, the
        public endpoint derives partial totals from the frozen ballot prefix.
        """
        if not p['published_phases'] or 'red' not in p['published_phases']:
            raise HTTPException(409, 'Голосование доступно после RED')
        secret = p.get('secret_show')
        if secret and secret['step'] != 4:
            raise HTTPException(409, 'Сначала заверши SECRET JACK SHOW')
        if len(p.get('revealed_slots', [])) != 3:
            raise HTTPException(409, 'Сначала раскрой всех трёх Secret Jacks')
        base = copy.deepcopy(p['ranking'])
        if len(base) != p['team_count']:
            raise HTTPException(409, 'Не сформирован рейтинг до голосования')
        if any(row.get('votes') for row in base):
            raise HTTPException(409, 'Нельзя повторно начислять голоса')
        mode = p['vote_mode']
        captains = {row['team_id']: row for row in p.get('captains', [])}
        entries = []
        for row in sorted(votes, key=lambda v: v['voter_team_id']):
            voter = int(row['voter_team_id'])
            target = int(row['target_team_id'])
            receiver = target if mode == 'target' else voter
            captain = captains.get(voter, {})
            entries.append({
                'voter_team_id': voter, 'target_team_id': target,
                'receiver_team_id': receiver,
                'voter_name': p['teams'][str(voter)],
                'target_name': p['teams'][str(target)],
                'receiver_name': p['teams'][str(receiver)],
                'captain_name': captain.get('name') or 'Капитан команды',
                'captain_player_id': captain.get('player_id') if captain.get('has_photo') else None,
                'points': 10000,
            })
        return {'step': 0, 'mode': mode, 'entries': entries, 'base_ranking': base}

    def vote_partial_ranking(snapshot, visible):
        # Recompute solely from previously revealed ballots: no future vote
        # may influence positions or cumulative totals on the public projector.
        ranked = copy.deepcopy(snapshot['base_ranking'])
        places = {r['team_id']: r['place'] for r in ranked}
        by_id = {r['team_id']: r for r in ranked}
        for row in visible:
            team = by_id[row['receiver_team_id']]
            team['votes'] += row['points']
            team['total'] += row['points']
        ranked.sort(key=lambda r: (-r['total'], r['team_id']))
        for index, row in enumerate(ranked):
            row['place'] = (ranked[index - 1]['place']
                            if index and ranked[index - 1]['total'] == row['total']
                            else index + 1)
            row['tied'] = sum(p['total'] == row['total'] for p in ranked) > 1
            row['before_place'] = places[row['team_id']]
            row['move'] = places[row['team_id']] - row['place']
        return ranked

    def final_snapshot(p):
        """Freeze final points and an explicit tie-resolved winner for ceremony.
        Actual competition places are never falsified to break score ties.
        """
        if set(PHASES) - set(p['published_phases']) or len(p['revealed_slots']) != 3 or not p['votes_published']:
            raise HTTPException(409, 'Сначала заверши GREEN, BLUE, RED, Secret Jack и голоса')
        if p.get('secret_show') and p['secret_show']['step'] != 4:
            raise HTTPException(409, 'SECRET JACK SHOW ещё не завершён')
        if p.get('vote_show') and p['vote_show']['step'] != len(p['vote_show']['entries']) + 1:
            raise HTTPException(409, 'Голоса капитанов ещё не раскрыты')
        ranking = copy.deepcopy(p['ranking'])
        if len(ranking) != p['team_count'] or len(ranking) < 3:
            raise HTTPException(409, 'Полный финальный рейтинг отсутствует')
        top_score = ranking[0]['total']
        tied_top = [r for r in ranking if r['total'] == top_score]
        decision = p.get('winner_decision')
        if len(tied_top) > 1 and decision not in [r['team_id'] for r in tied_top]:
            raise HTTPException(409, 'Ничья на первом месте: сначала выбери победителя в админке')
        champion = next((r for r in ranking if r['team_id'] == decision), ranking[0]) if len(tied_top) > 1 else ranking[0]
        # Ensure that the chosen tied winner is first on the ceremony podium.
        order = [champion] + [r for r in ranking if r['team_id'] != champion['team_id']]
        podium = []
        for i, row in enumerate(order[:3]):
            r = copy.deepcopy(row)
            r['ceremony_place'] = i + 1
            r['official_place'] = row['place']
            podium.append(r)
        return {'step': 0, 'ranking': ranking, 'podium': podium,
                'winner_team_id': champion['team_id'],
                'first_place_tie': len(tied_top) > 1}

    def require_admin(request: Request, write=False):
        if request.session.get('admin') is not True:
            raise HTTPException(401, 'Требуется вход администратора')
        if write:
            csrf = request.headers.get('x-csrf-token', '')
            if not csrf or not secrets.compare_digest(csrf, request.session.get('csrf', '')):
                raise HTTPException(403, 'Проверка CSRF не пройдена')
            origin = request.headers.get('origin')
            if origin:
                origin_base = f'{request.url.scheme}://{request.url.netloc}'
                forwarded = request.headers.get('x-forwarded-proto')
                if forwarded in ('https', 'http'):
                    origin_base = f'{forwarded}://{request.url.netloc}'
                if origin != origin_base:
                    raise HTTPException(403, 'Некорректный Origin')

    def check_team(c, value):
        team_id = strict_int(value, 'team_id')
        if not c.execute('SELECT 1 FROM teams WHERE team_id=?', (team_id,)).fetchone():
            raise HTTPException(422, f'Команда {team_id} неактивна')
        return team_id

    def strict_int(value: Any, label: str, lo: int | None = None, hi: int | None = None):
        if type(value) is not int or (lo is not None and value < lo) or (hi is not None and value > hi):
            raise HTTPException(422, f'{label}: недопустимое целое число')
        return value

    def public_safe(payload):
        # Never expose unpublished material in public JSON, including SSE.
        result = copy.deepcopy(payload)
        for stage in result.get('stages', {}).values():
            stage.pop('green_stack_actual', None)
        show = result.get('green_show')
        if show:
            count = len(show['ranking'])
            step = show['step']
            visible = list(reversed(show['ranking']))[:min(step, count)]
            result['green_view'] = {'count': count, 'step': step, 'max_step': count + 1,
                                    'revealed': visible}
            # The privately captured entire ranking must NEVER reach a public endpoint.
            result['green_show'] = {'step': step, 'max_step': count + 1}
            if step < count + 1:
                result['ranking'] = []
                result['stages'] = {}
                result['recent_changes'] = []
        blue_show = result.get('blue_show')
        if blue_show:
            count = len(blue_show['ranking'])
            step = blue_show['step']
            # Never deliver unrevealed BLUE totals or positions to the projector,
            # public JSON, or SSE before the organizer advances the scene.
            visible = list(reversed(blue_show['ranking']))[:min(step, count)]
            result['blue_view'] = {'count': count, 'step': step,
                                   'max_step': count + 1, 'revealed': visible}
            result['blue_show'] = {'step': step, 'max_step': count + 1}
            if step < count + 1:
                result['ranking'] = []
                result['stages'] = {}
                result['recent_changes'] = []
        red_show = result.get('red_show')
        if red_show:
            count = len(red_show['ranking'])
            step = red_show['step']
            visible = list(reversed(red_show['ranking']))[:min(step, count)]
            result['red_view'] = {'count': count, 'step': step,
                                  'max_step': count + 1, 'revealed': visible}
            # Private full ranking is omitted from all public response formats.
            result['red_show'] = {'step': step, 'max_step': count + 1}
            if step < count + 1:
                result['ranking'] = []
                result['stages'] = {}
                result['recent_changes'] = []
        secret_show = result.get('secret_show')
        if secret_show:
            step = secret_show['step']
            available = len(result['revealed_secrets'])
            visible = sorted(result['revealed_secrets'], key=lambda secret: secret['slot'])[:min(step, available)]
            result['secret_view'] = {
                'step': step, 'revealed_count': available,
                'max_step': available + (1 if available == 3 else 0),
                'revealed': visible,
                'summary': step == 4 and available == 3,
            }
            result['secret_show'] = {'step': step, 'revealed_count': available}
            result['revealed_secrets'] = visible
            result['revealed_slots'] = [secret['slot'] for secret in visible]
            # During cinematic replay, even previously announced Secret Jacks,
            # knockout bonuses and totals remain hidden until their reveal.
            if step < 4:
                result['ranking'] = []
                result['stages'] = {}
                result['recent_changes'] = []
        vote_show = result.get('vote_show')
        if vote_show:
            count = len(vote_show['entries'])
            step = vote_show['step']
            visible = vote_show['entries'][:min(step, count)]
            ranking = vote_partial_ranking(vote_show, visible)
            current = visible[-1].copy() if visible and step <= count else None
            if current:
                recipient = next(r for r in ranking if r['team_id'] == current['receiver_team_id'])
                current['place'] = recipient['place']
                current['before_place'] = recipient['before_place']
                current['total'] = recipient['total']
                current['vote_points'] = recipient['votes']
            result['vote_view'] = {
                'step': step, 'count': count, 'max_step': count + 1,
                'mode': vote_show['mode'], 'revealed': visible,
                'current': current, 'ranking': ranking,
                'summary': step == count + 1,
            }
            result['vote_show'] = {'step': step, 'count': count, 'max_step': count + 1}
            result['published_votes'] = [{'voter_team_id': r['voter_team_id'],
                                           'target_team_id': r['target_team_id']}
                                          for r in visible]
            result['ranking'] = ranking
            result['recent_changes'] = []
            result['votes_published'] = step == count + 1
        final_show = result.get('final_show')
        if final_show:
            step = final_show['step']
            podium = final_show['podium']
            revealed = ([podium[2]] if step >= 1 else []) + (
                [podium[1]] if step >= 2 else []) + (
                [podium[0]] if step >= 3 else [])
            result['final_view'] = {
                'step': step, 'max_step': 5, 'count': result['team_count'],
                'revealed': revealed,
                'current': ([podium[2], podium[1], podium[0]][step-1]
                            if 1 <= step <= 3 else None),
                'board': final_show['ranking'] if step >= 4 else [],
                'champion': podium[0] if step >= 5 else None,
                'tie_resolved': final_show['first_place_tie'] if step >= 3 else False,
                'roster': (result.get('roster', {}).get(str(podium[0]['team_id']), [])
                           if step >= 5 else []),
            }
            # No entire winner list or secret private snapshot over public JSON
            # until the conductor arrives at the complete board.
            result['final_show'] = {'step': step, 'max_step': 5}
            result.pop('vote_view', None)
            result.pop('red_view', None)
            result.pop('blue_view', None)
            result.pop('green_view', None)
            result['published_votes'] = []
            result['recent_changes'] = []
            if step < 4:
                result['ranking'] = []
                result['stages'] = {}
            else:
                # Canonical final standings, not vote-stage movement metadata.
                result['ranking'] = copy.deepcopy(final_show['ranking'])
            if step < 3:
                result['winner_decision'] = None
        return result

    def admin_state(c):
        version, published = get_pub(c)
        entries = {}
        for row in c.execute('SELECT * FROM teams ORDER BY team_id'):
            entries[row['team_id']] = rowdict(row)
        seats = [rowdict(r) for r in c.execute('''SELECT s.*,p.name AS player_name,p.photo_path IS NOT NULL AS has_photo
                  FROM seats s LEFT JOIN players p ON p.id=s.player_id ORDER BY s.table_no,s.box_no''')]
        stage = {r['team_id']: rowdict(r) for r in c.execute('SELECT * FROM stages')}
        secret_rows = [rowdict(r) for r in c.execute('''SELECT s.*,p.name AS player_name,st.team_id AS jack_team_id,st.table_no,st.box_no
                  FROM secrets s JOIN players p ON p.id=s.player_id JOIN seats st ON st.player_id=p.id ORDER BY slot''')]
        vote_rows = [rowdict(r) for r in c.execute('SELECT * FROM votes ORDER BY voter_team_id')]
        return {'csrf': None, 'team_count': team_count(c), 'vote_mode': setting(c, 'vote_mode'),
                'chip_settings': {'reentry': chip_setting(c, 'reentry'),
                                  'addon': chip_setting(c, 'addon')},
                'teams': list(entries.values()), 'seats': seats, 'stages': stage,
                'secrets': secret_rows, 'votes': vote_rows, 'publication_version': version,
                'published': published,
                'audit': [rowdict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 60')]}

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': 'sochi-show'}

    @app.get('/sochi/admin', response_class=HTMLResponse)
    def admin_page():
        return (HERE / 'static' / 'admin.html').read_text('utf-8')

    @app.get('/sochi/screen', response_class=HTMLResponse)
    def public_page():
        return (HERE / 'static' / 'screen.html').read_text('utf-8')

    @app.get('/sochi/preview/green', response_class=HTMLResponse)
    def green_preview():
        # Public DEMO: synthetic values only. Never reads database, sessions,
        # private scores, players or votes, and has no write capabilities.
        return (HERE / 'static' / 'green-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/blue', response_class=HTMLResponse)
    def blue_preview():
        # Demo-only results: cannot read or change tournament data.
        return (HERE / 'static' / 'blue-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/red', response_class=HTMLResponse)
    def red_preview():
        # Synthetic demo only; no authentication, tournament results or writes.
        return (HERE / 'static' / 'red-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/secret', response_class=HTMLResponse)
    def secret_preview():
        # Self-contained fictional rehearsal. No private draft or database reads.
        return (HERE / 'static' / 'secret-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/vote', response_class=HTMLResponse)
    def vote_preview():
        # Public rehearsal is populated entirely with fictional data.
        return (HERE / 'static' / 'vote-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/final', response_class=HTMLResponse)
    def final_preview():
        # Public demo is fictional, does not read or mutate live tournament.
        return (HERE / 'static' / 'final-preview.html').read_text('utf-8')

    @app.get('/sochi/preview/captains', response_class=HTMLResponse)
    def captains_preview():
        # Demo has no API calls; it cannot disclose or modify real captains.
        return (HERE / 'static' / 'captain-preview.html').read_text('utf-8')

    @app.post('/sochi/api/admin/login')
    async def login(request: Request):
        body = await request.json()
        client = request.client.host if request.client else 'unknown'
        now = time.monotonic()
        login_attempts[client] = [t for t in login_attempts.get(client, []) if now - t < 300]
        global_login_failures[:] = [t for t in global_login_failures if now - t < 3600]
        if len(login_attempts[client]) >= 8 or len(global_login_failures) >= 20:
            raise HTTPException(429, 'Слишком много попыток входа. Попробуйте позже')
        submitted = body.get('password', '')
        if not isinstance(submitted, str) or not secrets.compare_digest(submitted, password):
            login_attempts[client].append(now)
            global_login_failures.append(now)
            raise HTTPException(401, 'Неверный пароль')
        request.session.clear()
        request.session.update({'admin': True, 'csrf': secrets.token_urlsafe(32)})
        login_attempts.pop(client, None)
        return {'ok': True}

    @app.post('/sochi/api/admin/logout')
    async def logout(request: Request):
        require_admin(request, True)
        request.session.clear()
        return {'ok': True}

    @app.get('/sochi/api/admin/state')
    def get_admin_state(request: Request):
        require_admin(request)
        with connection() as c:
            state = admin_state(c)
        state['csrf'] = request.session['csrf']
        return state

    @app.get('/sochi/api/public/state')
    def get_public_state():
        with connection() as c:
            version, payload = get_pub(c)
        return {'version': version, 'state': public_safe(payload)}

    @app.get('/sochi/api/public/events')
    async def public_events(request: Request):
        async def events():
            last = -1
            while not await request.is_disconnected():
                with connection() as c:
                    version, payload = get_pub(c)
                if version != last:
                    yield 'event: state\ndata: ' + json.dumps({'version': version, 'state': public_safe(payload)}, ensure_ascii=False) + '\n\n'
                    last = version
                else:
                    yield ': heartbeat\n\n'
                await asyncio.sleep(2)
        return StreamingResponse(events(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @app.post('/sochi/api/admin/seating')
    async def import_seating(request: Request):
        require_admin(request, True)
        body = await request.json()
        count = strict_int(body.get('team_count'), 'team_count', 10, 13)
        document = body.get('document')
        if not isinstance(document, dict):
            raise HTTPException(422, 'Загрузите утверждённый JSON с variants')
        try:
            teams, cards = validate_seating(document, count)
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        with connection(write=True) as c:
            version, p = get_pub(c)
            if p['published_phases'] or p['revealed_slots'] or p['votes_published']:
                raise HTTPException(409, 'После публикации этапов рассадку менять нельзя')
            seats_assigned = c.execute('SELECT COUNT(*) FROM seats WHERE player_id IS NOT NULL').fetchone()[0]
            if seats_assigned and body.get('confirm_replace_cards') is not True:
                raise HTTPException(409, 'Карточки уже привязаны. Подтвердите физическую замену и повторите запрос')
            old_names = {r['team_id']: r['display_name'] for r in c.execute('SELECT * FROM teams')}
            old_seats = {r['card_id']: r['player_id'] for r in c.execute('SELECT * FROM seats')}
            if seats_assigned and any(card['card_id'] in old_seats and old_seats[card['card_id']] is not None
                                      and next((r for r in c.execute('SELECT team_id FROM seats WHERE card_id=?', (card['card_id'],))), None)['team_id'] != card['team_id']
                                      for card in cards if card['card_id'] in old_seats):
                raise HTTPException(409, 'Нельзя переносить занятую карточку в другую команду без ручной перепривязки')
            c.execute('DELETE FROM votes')
            c.execute('DELETE FROM secrets')
            c.execute('DELETE FROM stages')
            c.execute('DELETE FROM seats')
            c.execute('DELETE FROM teams')
            for t in teams:
                c.execute('INSERT INTO teams(team_id,original_name,display_name) VALUES (?,?,?)',
                          (t['team_id'], t['original_name'], old_names.get(t['team_id'], t['original_name'])))
                c.execute('INSERT INTO stages(team_id) VALUES (?)', (t['team_id'],))
            for card in cards:
                c.execute('INSERT INTO seats(card_id,team_id,table_no,box_no,player_id) VALUES (?,?,?,?,?)',
                          (card['card_id'], card['team_id'], card['table'], card['box'], old_seats.get(card['card_id'])))
            c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)', ('team_count', str(count)))
            # The public introduction remains frozen until an explicit publication.
            audit(c, 'seating-import', {'team_count': count, 'cards': len(cards), 'old_assigned': seats_assigned})
        return {'ok': True, 'cards': len(cards), 'occupancy': sorted({r['table'] for r in cards})}

    @app.post('/sochi/api/admin/player')
    async def update_player(request: Request):
        require_admin(request, True)
        body = await request.json()
        card_id, name = str(body.get('card_id', '')), str(body.get('name', '')).strip()
        if not name or len(name) > 90:
            raise HTTPException(422, 'Имя обязательно, максимум 90 символов')
        with connection(write=True) as c:
            seat = c.execute('SELECT * FROM seats WHERE card_id=?', (card_id,)).fetchone()
            if not seat:
                raise HTTPException(404, 'Карточка не найдена')
            if seat['player_id'] is not None and body.get('confirm_rebind') is not True:
                raise HTTPException(409, 'Игрок уже назначен; укажите confirm_rebind')
            if seat['player_id'] is None:
                pid = c.execute('INSERT INTO players(name) VALUES (?)', (name,)).lastrowid
                c.execute('UPDATE seats SET player_id=? WHERE card_id=?', (pid, card_id))
            else:
                pid = seat['player_id']
                c.execute('UPDATE players SET name=? WHERE id=?', (name, pid))
            audit(c, 'player-bind', {'card_id': card_id, 'player_id': pid})
        return {'ok': True, 'player_id': pid}

    @app.post('/sochi/api/admin/team')
    async def update_team(request: Request):
        require_admin(request, True)
        body = await request.json()
        with connection(write=True) as c:
            team_id = check_team(c, body.get('team_id'))
            if 'display_name' in body:
                name = str(body['display_name']).strip()
                if not 1 <= len(name) <= 45:
                    raise HTTPException(422, 'Название должно быть от 1 до 45 символов')
                duplicate = c.execute('SELECT team_id FROM teams WHERE display_name=? AND team_id<>?',
                                      (name, team_id)).fetchone()
                if duplicate and body.get('confirm_duplicate') is not True:
                    raise HTTPException(409, f'Название уже используется командой {duplicate[0]}')
                c.execute('UPDATE teams SET display_name=? WHERE team_id=?', (name, team_id))
                audit(c, 'team-rename-draft', {'team_id': team_id, 'name': name})
            if 'captain_player_id' in body:
                pid = body['captain_player_id']
                if pid is not None:
                    pid = strict_int(pid, 'captain_player_id', 1)
                    if not c.execute('SELECT 1 FROM seats WHERE player_id=? AND team_id=?', (pid, team_id)).fetchone():
                        raise HTTPException(422, 'Капитан должен принадлежать этой команде')
                c.execute('UPDATE teams SET captain_player_id=? WHERE team_id=?', (pid, team_id))
                audit(c, 'captain-update', {'team_id': team_id, 'player_id': pid})
        return {'ok': True}

    @app.post('/sochi/api/admin/chips-settings')
    async def update_chip_settings(request: Request):
        require_admin(request, True)
        body = await request.json()
        if not isinstance(body, dict) or not body or set(body) - {'reentry', 'addon'}:
            raise HTTPException(422, 'Передайте reentry и/или addon')
        with connection(write=True) as c:
            _, published = get_pub(c)
            for kind, value in body.items():
                strict_int(value, f'{kind}_chips_per_entry', 1, CHIP_LIMIT)
                phase = 'green' if kind == 'reentry' else 'blue'
                previous = chip_setting(c, kind)
                if phase in published['published_phases'] and value != previous:
                    raise HTTPException(409, f'{phase.upper()} уже опубликован: норматив фишек заблокирован')
            for kind, value in body.items():
                c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',
                          (f'{kind}_chips_per_entry', str(value)))
                amount_column = 'reentry_chips' if kind == 'reentry' else 'addon_chips'
                count_column = 'reentry_count' if kind == 'reentry' else 'addon_count'
                # Keep saved drafts coherent with the newly configured chip amount.
                c.execute(f'UPDATE stages SET {amount_column}={count_column}*? '
                          f'WHERE {count_column} IS NOT NULL', (value,))
            audit(c, 'chips-settings', {'configured': list(body)})
        return {'ok': True}

    @app.post('/sochi/api/admin/stage')
    async def update_stage(request: Request):
        require_admin(request, True)
        body = await request.json()
        if 'reentry_chips' in body or 'addon_chips' in body:
            raise HTTPException(422, 'Фишки рассчитываются автоматически: передайте только количество')
        fields = {k: v for k, v in body.items() if k in COLUMNS}
        if not fields:
            raise HTTPException(422, 'Не переданы поля этапа')
        for k, val in fields.items():
            strict_int(val, k, 1 if k == 'red_place' else 0,
                       3 if k == 'survivors' else COUNT_LIMIT if k in ('reentry_count', 'addon_count') else None)
        with connection(write=True) as c:
            team_id = check_team(c, body.get('team_id'))
            if 'red_place' in fields:
                strict_int(fields['red_place'], 'red_place', 1, team_count(c))
                clash = c.execute('SELECT team_id FROM stages WHERE red_place=? AND team_id<>?',
                                  (fields['red_place'], team_id)).fetchone()
                if clash:
                    raise HTTPException(409, f'Место RED уже у команды {clash[0]}')
            if 'reentry_count' in fields:
                fields['reentry_chips'] = fields['reentry_count'] * require_chip_setting(c, 'reentry')
            if 'addon_count' in fields:
                fields['addon_chips'] = fields['addon_count'] * require_chip_setting(c, 'addon')
            sets = ','.join(f'{k}=?' for k in fields)
            c.execute(f'UPDATE stages SET {sets} WHERE team_id=?', (*fields.values(), team_id))
            audit(c, 'stage-draft', {'team_id': team_id, 'fields': fields})
        return {'ok': True}

    @app.post('/sochi/api/admin/stages/bulk')
    async def save_stages_bulk(request: Request):
        require_admin(request, True)
        body = await request.json()
        phase, entries = body.get('phase'), body.get('teams')
        required = {'green': ('green_stack', 'reentry_count'),
                    'blue': ('blue_stack', 'addon_count', 'survivors'),
                    'red': ('red_place',)}.get(phase)
        if not required or not isinstance(entries, list):
            raise HTTPException(422, 'Ожидается phase=green|blue|red и список teams')
        with connection(write=True) as c:
            count = team_count(c)
            if len(entries) != count or {x.get('team_id') for x in entries if isinstance(x, dict)} != set(range(1, count + 1)):
                raise HTTPException(422, 'Нужен ровно один ряд на каждую активную команду')
            amount_per_entry = (require_chip_setting(c, 'reentry') if phase == 'green'
                                else require_chip_setting(c, 'addon') if phase == 'blue' else None)
            red_places = []
            for item in entries:
                if not isinstance(item, dict):
                    raise HTTPException(422, 'Некорректная строка')
                if 'reentry_chips' in item or 'addon_chips' in item:
                    raise HTTPException(422, 'Фишки рассчитываются автоматически: передайте только количество')
                if any(key not in item for key in required):
                    raise HTTPException(422, f'Команда {item.get("team_id")}: заполните все поля этапа')
                for key in required:
                    strict_int(item[key], key, 1 if key == 'red_place' else 0,
                               count if key == 'red_place' else 3 if key == 'survivors' else
                               COUNT_LIMIT if key in ('reentry_count', 'addon_count') else None)
                if phase == 'red':
                    red_places.append(item['red_place'])
            if phase == 'red' and sorted(red_places) != list(range(1, count + 1)):
                raise HTTPException(422, 'Места RED должны быть уникальными от 1 до N')
            for item in entries:
                fields = {key: item[key] for key in required}
                if phase == 'green':
                    fields['reentry_chips'] = item['reentry_count'] * amount_per_entry
                elif phase == 'blue':
                    fields['addon_chips'] = item['addon_count'] * amount_per_entry
                sets = ','.join(f'{key}=?' for key in fields)
                c.execute(f'UPDATE stages SET {sets} WHERE team_id=?', (*fields.values(), item['team_id']))
            audit(c, 'stage-bulk-draft', {'phase': phase, 'count': count})
        return {'ok': True}

    @app.post('/sochi/api/admin/vote')
    async def vote(request: Request):
        require_admin(request, True)
        body = await request.json()
        with connection(write=True) as c:
            a = check_team(c, body.get('voter_team_id'))
            b = check_team(c, body.get('target_team_id'))
            if a == b:
                raise HTTPException(422, 'Голосовать за свою команду нельзя')
            _, public = get_pub(c)
            if public['votes_published']:
                raise HTTPException(409, 'Голоса уже опубликованы и зафиксированы')
            c.execute('INSERT INTO votes(voter_team_id,target_team_id) VALUES (?,?) ON CONFLICT(voter_team_id) DO UPDATE SET target_team_id=excluded.target_team_id', (a, b))
            audit(c, 'vote-draft', {'voter_team_id': a})
        return {'ok': True}

    @app.post('/sochi/api/admin/vote-mode')
    async def vote_mode(request: Request):
        require_admin(request, True)
        body = await request.json()
        mode = body.get('mode')
        if mode not in ('target', 'voter'):
            raise HTTPException(422, 'mode=target|voter')
        with connection(write=True) as c:
            _, p = get_pub(c)
            if p['votes_published']:
                raise HTTPException(409, 'Режим голосов уже опубликован. Не допускается незаметная смена')
            c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)', ('vote_mode', mode))
            audit(c, 'vote-mode', {'mode': mode})
        return {'ok': True}

    @app.post('/sochi/api/admin/secret')
    async def save_secret(request: Request):
        require_admin(request, True)
        body = await request.json()
        slot = strict_int(body.get('slot'), 'slot', 1, 3)
        pid = strict_int(body.get('player_id'), 'player_id', 1)
        confirmed = body.get('confirmed') is True
        with connection(write=True) as c:
            _, p = get_pub(c)
            if slot in p['revealed_slots']:
                raise HTTPException(409, 'Jack уже раскрыт. Исправление только через отдельный запрос correction')
            if not c.execute('SELECT 1 FROM seats WHERE player_id=?', (pid,)).fetchone():
                raise HTTPException(422, 'Требуется игрок из активной рассадки')
            knockout_team_id = body.get('knockout_team_id')
            knockout_player_id = body.get('knockout_player_id')
            if confirmed:
                knockout_team_id = check_team(c, knockout_team_id)
                knockout_player_id = strict_int(knockout_player_id, 'knockout_player_id', 1)
                if not c.execute('SELECT 1 FROM seats WHERE player_id=? AND team_id=?', (knockout_player_id, knockout_team_id)).fetchone():
                    raise HTTPException(422, 'Выбивший игрок должен принадлежать команде выбившего')
            else:
                knockout_team_id, knockout_player_id = None, None
            try:
                c.execute('INSERT INTO secrets(slot,player_id,knockout_team_id,knockout_player_id,confirmed) VALUES (?,?,?,?,?) ON CONFLICT(slot) DO UPDATE SET player_id=excluded.player_id,knockout_team_id=excluded.knockout_team_id,knockout_player_id=excluded.knockout_player_id,confirmed=excluded.confirmed',
                          (slot, pid, knockout_team_id, knockout_player_id, int(confirmed)))
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, 'Игрок уже назначен другим Secret Jack') from exc
            audit(c, 'secret-draft', {'slot': slot, 'confirmed': confirmed})
        return {'ok': True}

    @app.post('/sochi/api/admin/secret-correction')
    async def correct_revealed_secret(request: Request):
        require_admin(request, True)
        raise HTTPException(409, 'Исправление раскрытого Secret Jack возможно только через защищённый редактор с PIN')

    @app.post('/sochi/api/admin/photo/{player_id}')
    async def upload_photo(request: Request, player_id: int, file: UploadFile = File(...)):
        require_admin(request, True)
        if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
            raise HTTPException(415, 'Разрешены JPEG/PNG/WEBP')
        raw = await file.read(5_000_001)
        if len(raw) > 5_000_000:
            raise HTTPException(413, 'Максимальный размер 5 МБ')
        try:
            img = Image.open(io.BytesIO(raw))
            img.verify()
            img = Image.open(io.BytesIO(raw))
            if img.format not in ('JPEG', 'PNG', 'WEBP') or img.width * img.height > 24_000_000:
                raise ValueError('Unsupported image')
            img = ImageOps.exif_transpose(img)
            img = ImageOps.fit(img.convert('RGB'), (560, 560), centering=(0.5, 0.42))
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(415, 'Повреждённое или небезопасное изображение') from exc
        with connection(write=True) as c:
            if not c.execute('SELECT 1 FROM seats WHERE player_id=?', (player_id,)).fetchone():
                raise HTTPException(404, 'Игрок не найден в текущем турнире')
            filename = secrets.token_hex(24) + '.webp'
            path = media / filename
            img.save(path, 'WEBP', quality=85, method=5)  # Removes source metadata/EXIF.
            old = c.execute('SELECT photo_path FROM players WHERE id=?', (player_id,)).fetchone()[0]
            c.execute('UPDATE players SET photo_path=? WHERE id=?', (filename, player_id))
            audit(c, 'photo-upload', {'player_id': player_id})
        # Keep previous file for safe correction/rollback. Garbage collection can be explicit later.
        return {'ok': True, 'player_id': player_id}

    @app.delete('/sochi/api/admin/photo/{player_id}')
    async def delete_photo(request: Request, player_id: int):
        require_admin(request, True)
        with connection(write=True) as c:
            row = c.execute('SELECT 1 FROM players WHERE id=?', (player_id,)).fetchone()
            if not row: raise HTTPException(404, 'Игрок не найден')
            c.execute('UPDATE players SET photo_path=NULL WHERE id=?', (player_id,))
            audit(c, 'photo-delete-draft', {'player_id': player_id})
        return {'ok': True, 'note': 'Публичное фото сохраняется до явного refresh-photo'}

    @app.get('/sochi/api/admin/photo/{player_id}')
    def admin_photo(request: Request, player_id: int):
        require_admin(request)
        with connection() as c:
            row = c.execute('SELECT photo_path FROM players WHERE id=?', (player_id,)).fetchone()
        if not row or not row['photo_path']:
            raise HTTPException(404, 'Нет фото')
        return FileResponse(media / Path(row['photo_path']).name, media_type='image/webp', headers={'Cache-Control': 'private,no-store'})

    @app.get('/sochi/api/public/photo/{player_id}')
    def public_photo(player_id: int):
        with connection() as c:
            _, p = get_pub(c)
            filename = p.get('visible_photos', {}).get(str(player_id))
            if player_id not in p.get('visible_player_ids', []) or not filename:
                raise HTTPException(404, 'Фотография не опубликована')
        return FileResponse(media / Path(filename).name, media_type='image/webp', headers={'Cache-Control': 'public,max-age=30'})

    def check_correction_version(version, body):
        supplied=body.get('expected_version')
        if type(supplied) is not int or supplied != version:
            raise HTTPException(409, 'Версия эфира изменилась. Обнови админку и проверь исправление заново')

    def make_correction(c, p, body):
        old=copy.deepcopy(p)
        edit=copy.deepcopy(body)
        edit['_winner_before']=p.get('winner_decision')
        if edit.get('kind')=='photo':
            edit['_photo_before']=p.get('visible_photos',{}).get(str(edit.get('player_id')))
        label,before,after=correction(c,edit)
        if edit.get('kind')=='winner':
            p['winner_decision']=after
        if edit.get('kind')=='seating_import':
            # A physical seating replacement is explicitly destructive.
            # Reset the live scenes, bonuses and rankings; draft players remain
            # bound only when their card and team were retained.
            p.clear()
            p.update(empty_public())
            p['scene']='pause'
        details=rebuild_corrected(c,p,green_snapshot,blue_snapshot,red_snapshot,final_snapshot,vote_snapshot)
        if edit.get('kind')=='seating_import':
            details['retracted_phases']=old.get('published_phases',[])
        # A protected edit is a live correction; the full authoritative score
        # table must be in sync even if the broadcast stays on its current step.
        result=score_delta(old,p)
        details['score_changes']=result
        return {'label':label, 'before':before, 'after':after,
                'old_scene':old.get('scene'),'new_scene':p.get('scene'),
                'old_phases':old.get('published_phases',[]),
                'new_phases':p.get('published_phases',[]),
                'old_leader':old.get('ranking',[{}])[0].get('name') if old.get('ranking') else None,
                'new_leader':p.get('ranking',[{}])[0].get('name') if p.get('ranking') else None,
                **details}

    @app.post('/sochi/api/admin/correction/preview')
    async def correction_preview(request: Request):
        require_admin(request, True)
        body=await request.json()
        if not isinstance(body,dict):
            raise HTTPException(422,'Нужен объект исправления')
        with connection(write=True) as c:
            version,p=get_pub(c)
            check_correction_version(version,body)
            summary=make_correction(c,p,body)
            # Preview must NEVER commit, audit or trigger live updates.
            c.rollback()
        return {'ok':True,'preview':summary,'expected_version':version}

    @app.post('/sochi/api/admin/correction/apply')
    async def correction_apply(request: Request):
        require_admin(request,True)
        body=await request.json()
        if not isinstance(body,dict):
            raise HTTPException(422,'Нужен объект исправления')
        client=request.client.host if request.client else 'unknown'
        now=time.monotonic()
        correction_failures[client]=[t for t in correction_failures.get(client,[]) if now-t<300]
        global_correction_failures[:]=[t for t in global_correction_failures if now-t<3600]
        if len(correction_failures[client])>=6 or len(global_correction_failures)>=15:
            raise HTTPException(429,'Защита PIN: слишком много попыток. Обратись к организатору')
        pin=body.get('pin')
        if not isinstance(pin,str) or not secrets.compare_digest(pin,password):
            correction_failures[client].append(now)
            global_correction_failures.append(now)
            raise HTTPException(403,'Неверный PIN подтверждения')
        correction_failures.pop(client,None)
        if body.get('confirm')!='ИСПРАВИТЬ':
            raise HTTPException(409,'Для подтверждения введи ИСПРАВИТЬ')
        reason=str(body.get('reason') or '').strip()
        if not 8<=len(reason)<=300:
            raise HTTPException(422,'Укажи причину изменения от 8 до 300 символов')
        with connection(write=True) as c:
            version,p=get_pub(c)
            check_correction_version(version,body)
            previous=copy.deepcopy(p)
            summary=make_correction(c,p,body)
            if summary['before']==summary['after']:
                raise HTTPException(409,'Данные не изменились')
            audit(c,'protected-correction',{
                'label':summary['label'],'before':summary['before'],
                'after':summary['after'],'reason':reason,
                'retracted':summary['retracted_phases']})
            new_version=save_public(c,p,'protected-correction')
            c.execute('''INSERT INTO correction_history(
                created_at,reason,field_name,previous_value,updated_value,
                previous_state,updated_state,publication_version)
                VALUES (?,?,?,?,?,?,?,?)''',
                (stamp(),reason,summary['label'],
                 json.dumps(summary['before'],ensure_ascii=False),
                 json.dumps(summary['after'],ensure_ascii=False),
                 json.dumps(previous,ensure_ascii=False),
                 json.dumps(p,ensure_ascii=False),new_version))
        return {'ok':True,'version':new_version,'summary':summary}

    @app.get('/sochi/api/admin/corrections/history')
    def correction_history(request: Request):
        require_admin(request)
        with connection() as c:
            rows=list(c.execute('''SELECT id,created_at,reason,field_name,
                previous_value,updated_value,publication_version
                FROM correction_history ORDER BY id DESC LIMIT 50'''))
        return {'history':[dict(row) for row in rows]}

    @app.post('/sochi/api/admin/publish')
    async def publish(request: Request):
        require_admin(request, True)
        body = await request.json()
        action = body.get('action')
        with connection(write=True) as c:
            _, p = get_pub(c)
            count = team_count(c)
            if not count:
                raise HTTPException(409, 'Сначала импортируйте утверждённую рассадку')
            if p['published_phases']:
                if action in ('teams','name','refresh-photo') or (
                    action == 'captains' and p.get('captains')):
                    raise HTTPException(409, 'Опубликованные данные исправляй через 🔐 Защищённое исправление с PIN')
            show = p.get('green_show')
            if show and action == 'green':
                raise HTTPException(409, 'GREEN SHOW уже запущен: повторная публикация GREEN требует отдельной процедуры исправления')
            if show and show['step'] < len(show['ranking']) + 1:
                if action in PHASES or (action == 'scene' and body.get('scene') in
                                        ('green', 'blue', 'red', 'final', 'winner')):
                    raise HTTPException(409, 'Сначала заверши раскрытие GREEN в шоу-пульте')
            blue_show = p.get('blue_show')
            if blue_show and action == 'blue':
                raise HTTPException(409, 'BLUE SHOW уже запущен: повторная публикация BLUE недоступна')
            if blue_show and blue_show['step'] < len(blue_show['ranking']) + 1:
                if action in PHASES or (action == 'scene' and body.get('scene') in
                                        ('green', 'blue', 'red', 'final', 'winner')):
                    raise HTTPException(409, 'Сначала заверши раскрытие BLUE в шоу-пульте')
            red_show = p.get('red_show')
            if red_show and action == 'red':
                raise HTTPException(409, 'RED SHOW уже запущен: повторная публикация RED недоступна')
            if red_show and red_show['step'] < len(red_show['ranking']) + 1:
                if (action in PHASES or action in ('reveal', 'votes', 'secret-show-start')
                    or (action == 'scene' and body.get('scene') in
                        ('green', 'blue', 'red', 'secrets', 'votes', 'final', 'winner'))):
                    raise HTTPException(409, 'Сначала заверши раскрытие RED в шоу-пульте')
            secret_show = p.get('secret_show')
            if secret_show and secret_show['step'] < 4:
                if (action in ('votes', 'red-show-start') or
                    (action == 'scene' and body.get('scene') in
                        ('secrets', 'votes', 'final', 'winner'))):
                    raise HTTPException(409, 'Сначала заверши раскрытие SECRET JACK SHOW')
            vote_show = p.get('vote_show')
            if vote_show and action == 'votes':
                raise HTTPException(409, 'Голоса уже зафиксированы для шоу. Повторная публикация запрещена')
            if vote_show and vote_show['step'] < len(vote_show['entries']) + 1:
                if (action in ('secret-show-start', 'winner-decision') or
                    (action == 'scene' and body.get('scene') in
                        ('votes', 'final', 'winner', 'secrets'))):
                    raise HTTPException(409, 'Сначала заверши раскрытие голосов капитанов')
            final_show = p.get('final_show')
            if final_show:
                if action in ('vote-show-start', 'vote-show-step', 'winner-decision'):
                    raise HTTPException(409, 'Финальный результат уже зафиксирован')
                if (final_show['step'] < 5 and action == 'scene' and
                    body.get('scene') in ('final', 'winner')):
                    raise HTTPException(409, 'Заверши FINAL SHOW в пульте организатора')
            if action == 'final-show-start':
                if not final_show:
                    p['final_show'] = final_snapshot(p)
                else:
                    p['final_show']['step'] = 0
                p['scene'] = 'final_show'
            elif action == 'final-show-step':
                if not final_show:
                    raise HTTPException(409, 'Сначала запусти FINAL SHOW')
                step = strict_int(body.get('step'), 'step', 0, 5)
                if abs(step - final_show['step']) != 1:
                    raise HTTPException(409, 'Переходи по одному финальному кадру')
                final_show['step'] = step
                p['scene'] = 'final_show'
            elif action == 'vote-show-start':
                if not vote_show or p['scene'] in ('final', 'winner'):
                    raise HTTPException(409, 'Сначала опубликуй голоса для шоу')
                vote_show['step'] = 0
                p['scene'] = 'vote_show'
            elif action == 'vote-show-step':
                if not vote_show or p['scene'] in ('final', 'winner'):
                    raise HTTPException(409, 'Сначала опубликуй голоса для шоу')
                step = strict_int(body.get('step'), 'step', 0, len(vote_show['entries']) + 1)
                if abs(step - vote_show['step']) != 1:
                    raise HTTPException(409, 'Переходи по одному голосу')
                vote_show['step'] = step
                p['scene'] = 'vote_show'
            elif action == 'secret-show-start':
                if 'red' not in p['published_phases'] or p['votes_published']:
                    raise HTTPException(409, 'SECRET JACK SHOW доступен после RED и до голосования')
                if len(list(c.execute('SELECT slot FROM secrets'))) != 3:
                    raise HTTPException(409, 'Сначала назначьте всех трёх Secret Jacks')
                p['secret_show'] = {'step': 0}
                p['scene'] = 'secret_show'
            elif action == 'secret-show-step':
                if not secret_show or p['votes_published']:
                    raise HTTPException(409, 'Сначала запусти SECRET JACK SHOW')
                available = len(p['revealed_secrets'])
                max_step = available + (1 if available == 3 else 0)
                step = strict_int(body.get('step'), 'step', 0, max_step)
                if abs(step - secret_show['step']) != 1:
                    raise HTTPException(409, 'Переходи по одному шагу')
                secret_show['step'] = step
                p['scene'] = 'secret_show'
            elif action == 'red-show-start':
                if 'red' not in p['published_phases'] or p['revealed_slots'] or p['votes_published']:
                    raise HTTPException(409, 'Шоу RED доступно после RED, до Secret Jack и голосов')
                if not red_show:
                    p['red_show'] = red_snapshot(p)
                else:
                    p['red_show']['step'] = 0
                p['scene'] = 'red_show'
            elif action == 'red-show-step':
                if not red_show or p['revealed_slots'] or p['votes_published']:
                    raise HTTPException(409, 'Сначала запусти RED SHOW')
                step = strict_int(body.get('step'), 'step', 0, len(red_show['ranking']) + 1)
                if abs(step - red_show['step']) != 1:
                    raise HTTPException(409, 'Переходи по одному шагу')
                red_show['step'] = step
                p['scene'] = 'red_show'
            elif action == 'blue-show-start':
                if 'blue' not in p['published_phases'] or 'red' in p['published_phases']:
                    raise HTTPException(409, 'Шоу BLUE доступно после BLUE и до RED')
                if not blue_show:
                    p['blue_show'] = blue_snapshot(p)
                else:
                    p['blue_show']['step'] = 0
                p['scene'] = 'blue_show'
            elif action == 'blue-show-step':
                if not blue_show or 'red' in p['published_phases']:
                    raise HTTPException(409, 'Сначала запусти BLUE SHOW')
                last_step = blue_show['step']
                step = strict_int(body.get('step'), 'step', 0, len(blue_show['ranking']) + 1)
                if abs(step - last_step) != 1:
                    raise HTTPException(409, 'Переходи по одному шагу')
                blue_show['step'] = step
                p['scene'] = 'blue_show'
            elif action == 'green-show-start':
                if 'green' not in p['published_phases'] or 'blue' in p['published_phases']:
                    raise HTTPException(409, 'Шоу GREEN доступно после GREEN и до BLUE')
                if not show:
                    p['green_show'] = green_snapshot(p)
                else:
                    p['green_show']['step'] = 0
                p['scene'] = 'green_show'
            elif action == 'green-show-step':
                if not show:
                    raise HTTPException(409, 'Сначала запусти GREEN SHOW')
                last_step = show['step']
                step = strict_int(body.get('step'), 'step', 0, len(show['ranking']) + 1)
                if abs(step - last_step) != 1:
                    raise HTTPException(409, 'Переходи по одному шагу')
                show['step'] = step
                p['scene'] = 'green_show'
            elif action == 'teams':
                p['team_count'] = count
                p['teams'] = {str(r['team_id']): r['display_name'] for r in c.execute('SELECT * FROM teams')}
                p['roster'] = {str(tid): [r['name'] for r in c.execute('''SELECT p.name FROM seats s JOIN players p ON p.id=s.player_id
                                  WHERE s.team_id=? ORDER BY s.table_no''', (tid,))] for tid in range(1, count+1)}
                p['scene'] = 'teams'
            elif action == 'refresh-photo':
                pid = strict_int(body.get('player_id'), 'player_id', 1)
                if pid not in p.get('visible_player_ids', []):
                    raise HTTPException(409, 'Игрок ещё не опубликован')
                row = c.execute('SELECT photo_path FROM players WHERE id=?', (pid,)).fetchone()
                if not row: raise HTTPException(404, 'Игрок не найден')
                if row['photo_path']:
                    p.setdefault('visible_photos', {})[str(pid)] = row['photo_path']
                else:
                    p.setdefault('visible_photos', {}).pop(str(pid), None)
                for sec in p['revealed_secrets']:
                    if sec['player_id'] == pid: sec['has_photo'] = bool(row['photo_path'])
                for cap in p['captains']:
                    if cap['player_id'] == pid: cap['has_photo'] = bool(row['photo_path'])
            elif action == 'name':
                team_id = check_team(c, body.get('team_id'))
                name = c.execute('SELECT display_name FROM teams WHERE team_id=?', (team_id,)).fetchone()[0]
                p['teams'][str(team_id)] = name
            elif action == 'captains':
                captains = []
                visible = set(p.get('visible_player_ids', []))
                for row in c.execute('''SELECT t.team_id,t.captain_player_id,p.name,p.photo_path FROM teams t
                                        LEFT JOIN players p ON p.id=t.captain_player_id ORDER BY t.team_id'''):
                    item = {'team_id': row['team_id'], 'name': row['name'] or 'Капитан не выбран',
                            'player_id': row['captain_player_id'], 'has_photo': bool(row['photo_path'])}
                    captains.append(item)
                    if row['captain_player_id'] is not None:
                        visible.add(row['captain_player_id'])
                p['captains'] = captains
                p['visible_player_ids'] = sorted(visible)
                p.setdefault('visible_photos', {})
                for item in captains:
                    if item['player_id'] is not None:
                        photo = c.execute('SELECT photo_path FROM players WHERE id=?', (item['player_id'],)).fetchone()[0]
                        if photo: p['visible_photos'][str(item['player_id'])] = photo
                p['scene'] = 'captains'
            elif action in PHASES:
                if not p['teams']:
                    raise HTTPException(409, 'Сначала опубликуйте команды')
                rows = list(c.execute('SELECT * FROM stages ORDER BY team_id'))
                if len(rows) != count:
                    raise HTTPException(409, 'Несоответствие количества команд')
                if action == 'red':
                    places = [r['red_place'] for r in rows]
                    if any(place is None for place in places) or sorted(places) != list(range(1, count + 1)):
                        raise HTTPException(422, 'RED: места 1..N без пропусков и повторов')
                for r in rows:
                    team_id = str(r['team_id'])
                    p['stages'].setdefault(team_id, {})
                    if action == 'green':
                        if any(r[key] is None for key in ('green_stack', 'reentry_count', 'reentry_chips')):
                            raise HTTPException(422, 'GREEN: заполните стеки и количество re-entry')
                        rate = require_chip_setting(c, 'reentry')
                        if r['reentry_chips'] != r['reentry_count'] * rate:
                            raise HTTPException(409, 'GREEN: сумма re-entry не соответствует настройкам')
                        score = green_points(r['green_stack'], r['reentry_chips'])
                        p['stages'][team_id]['green_stack_actual'] = r['green_stack']
                    elif action == 'blue':
                        if 'green' not in p['published_phases']:
                            raise HTTPException(409, 'Перед BLUE необходимо опубликовать GREEN')
                        if any(r[key] is None for key in ('blue_stack', 'addon_count', 'addon_chips', 'survivors')):
                            raise HTTPException(422, 'BLUE: заполните стек, количество add-on и выживших')
                        rate = require_chip_setting(c, 'addon')
                        if r['addon_chips'] != r['addon_count'] * rate:
                            raise HTTPException(409, 'BLUE: сумма add-on не соответствует настройкам')
                        score = blue_points(p['stages'][team_id]['green_stack_actual'], r['blue_stack'], r['addon_chips'], r['survivors'])
                    else:
                        score = red_points(r['red_place'], count)
                    p['stages'][team_id][action] = score
                if action not in p['published_phases']:
                    p['published_phases'].append(action)
                if action == 'green' and body.get('show_mode') == 'cinematic':
                    # Freeze scores and open a spoiler-free GREEN intro atomically.
                    p['green_show'] = green_snapshot(p)
                    p['scene'] = 'green_show'
                elif action == 'blue' and body.get('show_mode') == 'cinematic':
                    # Freeze cumulative GREEN+BLUE and enter BLUE intro atomically.
                    # Even the first public response must not contain BLUE totals.
                    p['blue_show'] = blue_snapshot(p)
                    p['scene'] = 'blue_show'
                elif action == 'red' and body.get('show_mode') == 'cinematic':
                    # Atomic capture: no RED score leaks on the first SSE frame.
                    p['red_show'] = red_snapshot(p)
                    p['scene'] = 'red_show'
                else:
                    p['scene'] = action
            elif action == 'reveal':
                if not p['teams']:
                    raise HTTPException(409, 'Сначала опубликуйте команды')
                slot = strict_int(body.get('slot'), 'slot', 1, 3)
                if slot in p['revealed_slots']:
                    raise HTTPException(409, 'Jack уже раскрыт; повторите только анимацию на экране')
                if len(list(c.execute('SELECT slot FROM secrets'))) != 3:
                    raise HTTPException(409, 'Назначьте всех 3 Secret Jacks до раскрытия')
                if slot != len(p['revealed_slots']) + 1:
                    raise HTTPException(409, 'Раскрытие строго по одному: 1, 2, 3')
                if secret_show and secret_show['step'] != len(p['revealed_slots']):
                    raise HTTPException(409, 'Сначала вернись к последнему раскрытому Jack')
                sec = c.execute('''SELECT s.*,p.name, p.photo_path,st.team_id AS jack_team_id FROM secrets s
                                    JOIN players p ON p.id=s.player_id JOIN seats st ON st.player_id=p.id WHERE slot=?''', (slot,)).fetchone()
                if not sec:
                    raise HTTPException(404, 'Jack не назначен')
                p['team_count'] = count
                p['revealed_slots'].append(slot)
                p['revealed_secrets'].append({'slot': slot, 'player_id': sec['player_id'],
                                              'name': sec['name'], 'jack_team_id': sec['jack_team_id'],
                                              'knockout_team_id': sec['knockout_team_id'], 'knockout_player_id': sec['knockout_player_id'],
                                              'knockout_name': (c.execute('SELECT name FROM players WHERE id=?', (sec['knockout_player_id'],)).fetchone() or {'name': None})['name'],
                                              'confirmed': bool(sec['confirmed']), 'has_photo': bool(sec['photo_path'])})
                visible = set(p.get('visible_player_ids', []))
                visible.add(sec['player_id'])
                p['visible_player_ids'] = sorted(visible)
                if sec['photo_path']:
                    p.setdefault('visible_photos', {})[str(sec['player_id'])] = sec['photo_path']
                if secret_show:
                    # Replays only change scene step; this first publish assigns
                    # the bonus exactly once through revealed_secrets.
                    secret_show['step'] = slot
                    p['scene'] = 'secret_show'
                else:
                    p['scene'] = 'secrets'
            elif action == 'votes':
                votes = [rowdict(r) for r in c.execute('SELECT * FROM votes')]
                if len(votes) != count:
                    raise HTTPException(422, 'Нужно по одному голосу каждой команды')
                p['vote_mode'] = setting(c, 'vote_mode')
                if body.get('show_mode') == 'cinematic':
                    # All votes are frozen privately; the intro exposes none.
                    # Award points in the same existing published_ranking path.
                    p['vote_show'] = vote_snapshot(p, votes)
                    p['scene'] = 'vote_show'
                else:
                    p['scene'] = 'votes'
                p['published_votes'] = votes
                p['votes_published'] = True
            elif action == 'scene':
                scene = body.get('scene')
                if scene not in SCENES:
                    raise HTTPException(422, 'Неизвестная сцена')
                if scene in PHASES and scene not in p['published_phases']:
                    raise HTTPException(409, 'Этап ещё не опубликован')
                if scene in ('final', 'winner') and (set(PHASES) - set(p['published_phases']) or
                                                       len(p['revealed_slots']) != 3 or not p['votes_published']):
                    raise HTTPException(409, 'Финал доступен после публикации всех этапов и бонусов')
                if scene == 'winner' and len(p['ranking']) >= 2 and p['ranking'][0]['total'] == p['ranking'][1]['total'] and not p.get('winner_decision'):
                    raise HTTPException(409, 'Ничья: требуется решение организатора')
                p['scene'] = scene
            elif action == 'winner-decision':
                winning_team_id = check_team(c, body.get('team_id'))
                if not p['ranking'] or winning_team_id not in [r['team_id'] for r in p['ranking'] if r['total'] == p['ranking'][0]['total']]:
                    raise HTTPException(422, 'Решение допустимо только среди команд с равным максимумом')
                p['winner_decision'] = winning_team_id
            else:
                raise HTTPException(422, 'Неизвестное действие публикации')
            # Publication copies draft into a frozen public snapshot. Only this path changes public state.
            version = save_public(c, p, action=f'publish-{action}')
        return {'ok': True, 'version': version}

    @app.get('/sochi/api/admin/export.csv')
    def export_csv(request: Request):
        require_admin(request)
        import csv
        with connection() as c:
            data = admin_state(c)
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(['Команда', 'Оригинал', 'Название', 'GREEN', 'BLUE', 'RED', 'Secret Jack', 'Голоса', 'Итого'])
        ranking = {r['team_id']: r for r in data['published']['ranking']}
        for t in data['teams']:
            r = ranking.get(t['team_id'], {})
            writer.writerow([t['team_id'], t['original_name'], t['display_name'],
                             *[r.get(k, 0) for k in ('green', 'blue', 'red', 'secret', 'votes', 'total')]])
        return StreamingResponse(iter([b'\xef\xbb\xbf', stream.getvalue().encode('utf-8')]),
                                 media_type='text/csv; charset=utf-8',
                                 headers={'Content-Disposition': 'attachment; filename="sochi-protocol.csv"'})

    return app


# Never load missing secrets in production: the process must fail closed at boot.
if os.environ.get('SOCHI_ADMIN_PASSWORD') and os.environ.get('SOCHI_SESSION_SECRET'):
    app = app_factory()
else:
    # ASGI imports should still be safe for test tooling; health cannot run until configured.
    app = FastAPI(title='SOCHI SHOW not configured')

    @app.get('/health')
    def missing_configuration():
        return JSONResponse({'status': 'configuration-required'}, status_code=503)
