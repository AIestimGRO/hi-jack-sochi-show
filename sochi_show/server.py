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

HERE = Path(__file__).resolve().parent
SCENES = {'intro', 'teams', 'green', 'blue', 'captains', 'red', 'secrets', 'votes', 'final', 'winner', 'pause'}
PHASES = ('green', 'blue', 'red')
COLUMNS = ('green_stack', 'reentry_chips', 'blue_stack', 'addon_chips', 'survivors', 'red_place', 'reentry_count')


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
            CREATE TABLE IF NOT EXISTS stages (team_id INTEGER PRIMARY KEY,green_stack INTEGER,reentry_chips INTEGER,reentry_count INTEGER,blue_stack INTEGER,addon_chips INTEGER,survivors INTEGER,red_place INTEGER);
            CREATE TABLE IF NOT EXISTS secrets (slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 3),player_id INTEGER NOT NULL UNIQUE,knockout_team_id INTEGER,knockout_player_id INTEGER,confirmed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS votes (voter_team_id INTEGER PRIMARY KEY,target_team_id INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS publication (id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,action TEXT NOT NULL,data TEXT NOT NULL);
        ''')
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

    def get_pub(c):
        row = c.execute('SELECT version,payload FROM publication WHERE id=1').fetchone()
        return row['version'], json.loads(row['payload'])

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
        state['recent_changes'] = [
            {'team_id': e['team_id'], 'from': old_places[e['team_id']], 'to': e['place']}
            for e in state['ranking'] if e['team_id'] in old_places and old_places[e['team_id']] != e['place']
        ]
        c.execute('UPDATE publication SET version=?,payload=? WHERE id=1',
                  (previous_version + 1, json.dumps(state, ensure_ascii=False)))
        audit(c, action, {'version': previous_version + 1, 'scene': state['scene']})
        return previous_version + 1

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
        # Internal frozen GREEN stacks are used for BLUE math, but must not
        # appear in HTML, public JSON or SSE responses.
        result = copy.deepcopy(payload)
        for stage in result.get('stages', {}).values():
            stage.pop('green_stack_actual', None)
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

    @app.post('/sochi/api/admin/stage')
    async def update_stage(request: Request):
        require_admin(request, True)
        body = await request.json()
        fields = {k: v for k, v in body.items() if k in COLUMNS}
        if not fields:
            raise HTTPException(422, 'Не переданы поля этапа')
        for k, val in fields.items():
            strict_int(val, k, 1 if k == 'red_place' else 0,
                       3 if k == 'survivors' else None)
        with connection(write=True) as c:
            team_id = check_team(c, body.get('team_id'))
            if 'red_place' in fields:
                strict_int(fields['red_place'], 'red_place', 1, team_count(c))
                clash = c.execute('SELECT team_id FROM stages WHERE red_place=? AND team_id<>?',
                                  (fields['red_place'], team_id)).fetchone()
                if clash:
                    raise HTTPException(409, f'Место RED уже у команды {clash[0]}')
            sets = ','.join(f'{k}=?' for k in fields)
            c.execute(f'UPDATE stages SET {sets} WHERE team_id=?', (*fields.values(), team_id))
            audit(c, 'stage-draft', {'team_id': team_id, 'fields': fields})
        return {'ok': True}

    @app.post('/sochi/api/admin/stages/bulk')
    async def save_stages_bulk(request: Request):
        require_admin(request, True)
        body = await request.json()
        phase, entries = body.get('phase'), body.get('teams')
        required = {'green': ('green_stack', 'reentry_chips', 'reentry_count'),
                    'blue': ('blue_stack', 'addon_chips', 'survivors'),
                    'red': ('red_place',)}.get(phase)
        if not required or not isinstance(entries, list):
            raise HTTPException(422, 'Ожидается phase=green|blue|red и список teams')
        with connection(write=True) as c:
            count = team_count(c)
            if len(entries) != count or {x.get('team_id') for x in entries if isinstance(x, dict)} != set(range(1, count + 1)):
                raise HTTPException(422, 'Нужен ровно один ряд на каждую активную команду')
            red_places = []
            for item in entries:
                if not isinstance(item, dict):
                    raise HTTPException(422, 'Некорректная строка')
                if any(key not in item for key in required):
                    raise HTTPException(422, f'Команда {item.get("team_id")}: заполните все поля этапа')
                for key in required:
                    strict_int(item[key], key, 1 if key == 'red_place' else 0,
                               count if key == 'red_place' else 3 if key == 'survivors' else None)
                if phase == 'red': red_places.append(item['red_place'])
            if phase == 'red' and sorted(red_places) != list(range(1, count + 1)):
                raise HTTPException(422, 'Места RED должны быть уникальными от 1 до N')
            for item in entries:
                sets = ','.join(f'{key}=?' for key in required)
                c.execute(f'UPDATE stages SET {sets} WHERE team_id=?',
                          (*[item[key] for key in required], item['team_id']))
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
        body = await request.json()
        slot = strict_int(body.get('slot'), 'slot', 1, 3)
        pid = strict_int(body.get('player_id'), 'player_id', 1)
        if body.get('confirm_correction') is not True:
            raise HTTPException(409, 'Для исправления опубликованной роли требуется явное подтверждение')
        confirmed = body.get('confirmed') is True
        with connection(write=True) as c:
            _, p = get_pub(c)
            if slot not in p['revealed_slots']:
                raise HTTPException(409, 'Исправление допускается только для раскрытого Jack')
            player = c.execute('''SELECT p.name,p.photo_path,s.team_id FROM seats s
                                  JOIN players p ON p.id=s.player_id WHERE s.player_id=?''', (pid,)).fetchone()
            if not player:
                raise HTTPException(422, 'Игрок должен быть в активной рассадке')
            receiver = body.get('knockout_team_id')
            knockout_pid = body.get('knockout_player_id')
            if confirmed:
                receiver = check_team(c, receiver)
                knockout_pid = strict_int(knockout_pid, 'knockout_player_id', 1)
                if not c.execute('SELECT 1 FROM seats WHERE player_id=? AND team_id=?', (knockout_pid, receiver)).fetchone():
                    raise HTTPException(422, 'Выбивший игрок должен принадлежать указанной команде')
            else:
                receiver, knockout_pid = None, None
            try:
                c.execute('UPDATE secrets SET player_id=?,knockout_team_id=?,knockout_player_id=?,confirmed=? WHERE slot=?',
                          (pid, receiver, knockout_pid, int(confirmed), slot))
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, 'Игрок уже назначен другим Secret Jack') from exc
            for secret in p['revealed_secrets']:
                if secret['slot'] == slot:
                    secret.update({'player_id': pid, 'name': player['name'], 'has_photo': bool(player['photo_path']),
                                   'jack_team_id': player['team_id'], 'knockout_team_id': receiver, 'knockout_player_id': knockout_pid, 'knockout_name': (c.execute('SELECT name FROM players WHERE id=?', (knockout_pid,)).fetchone() or {'name': None})['name'], 'confirmed': confirmed})
            visible = {x['player_id'] for x in p['revealed_secrets']}
            visible.update(x['player_id'] for x in p['captains'] if x['player_id'])
            p['visible_player_ids'] = sorted(visible)
            p['visible_photos'] = {str(k): v for k, v in p.get('visible_photos', {}).items() if int(k) in visible}
            if player['photo_path']:
                p['visible_photos'][str(pid)] = player['photo_path']
            p['scene'] = 'secrets'
            audit(c, 'revealed-secret-correction', {'slot': slot, 'player_id': pid, 'receiver': receiver})
            version = save_public(c, p, 'publish-revealed-secret-correction')
        return {'ok': True, 'version': version}

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
            if action == 'teams':
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
                        if any(r[key] is None for key in ('green_stack', 'reentry_chips')):
                            raise HTTPException(422, 'GREEN: все стеки и re-entry обязательны')
                        score = green_points(r['green_stack'], r['reentry_chips'])
                        p['stages'][team_id]['green_stack_actual'] = r['green_stack']
                    elif action == 'blue':
                        if 'green' not in p['published_phases']:
                            raise HTTPException(409, 'Перед BLUE необходимо опубликовать GREEN')
                        if any(r[key] is None for key in ('green_stack', 'blue_stack', 'addon_chips', 'survivors')):
                            raise HTTPException(422, 'BLUE: заполните стеки, add-on и survivors')
                        score = blue_points(p['stages'][team_id]['green_stack_actual'], r['blue_stack'], r['addon_chips'], r['survivors'])
                    else:
                        score = red_points(r['red_place'], count)
                    p['stages'][team_id][action] = score
                if action not in p['published_phases']:
                    p['published_phases'].append(action)
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
                p['scene'] = 'secrets'
            elif action == 'votes':
                votes = [rowdict(r) for r in c.execute('SELECT * FROM votes')]
                if len(votes) != count:
                    raise HTTPException(422, 'Нужно по одному голосу каждой команды')
                p['published_votes'] = votes
                p['votes_published'] = True
                p['vote_mode'] = setting(c, 'vote_mode')
                p['scene'] = 'votes'
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
