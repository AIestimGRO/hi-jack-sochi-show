"""Protected tournament corrections, consistently rebuilding published show snapshots.

All edits are made within the caller's BEGIN IMMEDIATE transaction.
No public data is modified on preview (the caller rolls the transaction back).
"""
import copy
import sqlite3
from fastapi import HTTPException
from .core import green_points, blue_points, red_points, published_ranking, validate_seating

FIELD_LIMITS = {
    'green_stack': (0, None), 'reentry_count': (0, 1000),
    'blue_stack': (0, None), 'addon_count': (0, 1000),
    'survivors': (0, 3), 'red_place': (1, None),
}
PHASES = ('green', 'blue', 'red')
REQUIRED = {'green': ('green_stack','reentry_count'),
            'blue': ('blue_stack','addon_count','survivors'),
            'red': ('red_place',)}


def fail(code, message):
    raise HTTPException(code, message)


def integer(value, name, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        fail(422, f'{name}: требуется целое число от {low}'+(f' до {high}' if high is not None else ''))
    return value


def team(c, value):
    number = integer(value, 'team_id', 1)
    if not c.execute('SELECT 1 FROM teams WHERE team_id=?', (number,)).fetchone():
        fail(422, 'Команда не найдена')
    return number


def active_player(c, value, tid=None):
    pid = integer(value, 'player_id', 1)
    row = c.execute('SELECT s.team_id, p.name FROM seats s JOIN players p ON p.id=s.player_id WHERE s.player_id=?', (pid,)).fetchone()
    if row is None or (tid is not None and row['team_id'] != tid):
        fail(422, 'Выберите игрока из активной рассадки'+(' указанной команды' if tid else ''))
    return pid


def current_rate(c, kind):
    row = c.execute('SELECT value FROM settings WHERE key=?',(f'{kind}_chips_per_entry',)).fetchone()
    return int(row['value']) if row else None


def correction(c, body):
    """Mutates SQL rows; returns a human-readable before / after change pair."""
    kind = body.get('kind')
    value = body.get('value')
    clear = body.get('clear') is True
    if kind == 'team_name':
        tid = team(c, body.get('team_id'))
        old = c.execute('SELECT display_name FROM teams WHERE team_id=?',(tid,)).fetchone()[0]
        new = str(value or '').strip()
        if not 1 <= len(new) <= 45:
            fail(422, 'Название команды: от 1 до 45 символов')
        duplicate = c.execute('SELECT team_id FROM teams WHERE display_name=? AND team_id<>?', (new,tid)).fetchone()
        if duplicate:
            fail(409, f'Название уже используется командой №{duplicate[0]}')
        c.execute('UPDATE teams SET display_name=? WHERE team_id=?',(new,tid))
        return f'Название команды №{tid}', old, new
    if kind == 'captain':
        tid = team(c, body.get('team_id'))
        row = c.execute('SELECT captain_player_id FROM teams WHERE team_id=?',(tid,)).fetchone()
        new = None if clear else active_player(c,value,tid)
        c.execute('UPDATE teams SET captain_player_id=? WHERE team_id=?',(new,tid))
        return f'Капитан команды №{tid}',row['captain_player_id'],new
    if kind == 'player_name':
        pid = active_player(c,body.get('player_id'))
        old = c.execute('SELECT name FROM players WHERE id=?',(pid,)).fetchone()[0]
        new = str(value or '').strip()
        if not 1 <= len(new) <= 90:
            fail(422,'Имя игрока: от 1 до 90 символов')
        c.execute('UPDATE players SET name=? WHERE id=?',(new,pid))
        return f'Имя игрока #{pid}',old,new
    if kind == 'seat':
        card = str(body.get('card_id') or '')
        row = c.execute('SELECT player_id,team_id FROM seats WHERE card_id=?',(card,)).fetchone()
        if not row: fail(422,'Карточка рассадки не найдена')
        old = row['player_id']
        if clear:
            new = None
        elif value is not None and type(value) is int:
            new = active_player(c,value,row['team_id'])
            if new != old:
                occupied=c.execute('SELECT card_id FROM seats WHERE player_id=?',(new,)).fetchone()
                if occupied:
                    # Swap players only within the same team; preserve cards and team membership.
                    c.execute('UPDATE seats SET player_id=NULL WHERE card_id=?',(occupied['card_id'],))
                    c.execute('UPDATE seats SET player_id=? WHERE card_id=?',(old,occupied['card_id']))
        else:
            name=str(value or '').strip()
            if not 1 <= len(name) <= 90: fail(422,'Укажи имя нового игрока или его ID')
            new=c.execute('INSERT INTO players(name) VALUES (?)',(name,)).lastrowid
        c.execute('UPDATE seats SET player_id=? WHERE card_id=?',(new,card))
        return f'Игрок карточки {card}',old,new
    if kind == 'chip_rate':
        rate = body.get('field')
        if rate not in ('reentry','addon'): fail(422,'Выбери reentry или addon')
        old = current_rate(c,rate)
        new = integer(value,rate,1,1_000_000_000)
        c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',(f'{rate}_chips_per_entry',str(new)))
        c.execute(f'UPDATE stages SET {"reentry" if rate=="reentry" else "addon"}_chips={"reentry" if rate=="reentry" else "addon"}_count * ? WHERE {"reentry" if rate=="reentry" else "addon"}_count IS NOT NULL',(new,))
        return f'Норматив {rate}, фишек за 1',old,new
    if kind == 'stage':
        tid=team(c,body.get('team_id'))
        field=body.get('field')
        if field not in FIELD_LIMITS: fail(422,'Недопустимое поле этапа')
        old=c.execute(f'SELECT {field} FROM stages WHERE team_id=?',(tid,)).fetchone()
        if not old:fail(422,'Строка этапа не найдена')
        low,high=FIELD_LIMITS[field]
        if field=='red_place':
            high=c.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
        new=None if clear else integer(value,field,low,high)
        # A RED place correction swaps the conflicting place rather than leaving duplicates.
        if field=='red_place' and new is not None:
            competing=c.execute('SELECT team_id FROM stages WHERE red_place=? AND team_id<>?',(new,tid)).fetchone()
            if competing:
                c.execute('UPDATE stages SET red_place=? WHERE team_id=?',(old[field],competing['team_id']))
        c.execute(f'UPDATE stages SET {field}=? WHERE team_id=?',(new,tid))
        if field in ('reentry_count','addon_count'):
            name = 'reentry' if field=='reentry_count' else 'addon'
            rate = current_rate(c,name)
            if rate is None and new is not None: fail(409,f'Сначала задай норматив {name}')
            c.execute(f'UPDATE stages SET {name}_chips=? WHERE team_id=?',(None if new is None else new*rate,tid))
        return f'{field} команды №{tid}',old[field],new
    if kind == 'photo':
        pid=active_player(c,body.get('player_id'))
        row=c.execute('SELECT photo_path FROM players WHERE id=?',(pid,)).fetchone()
        old=body.get('_photo_before')
        if clear:
            c.execute('UPDATE players SET photo_path=NULL WHERE id=?',(pid,))
            return f'Фото игрока #{pid}',old,None
        if row['photo_path'] is None:
            fail(409,'Сначала загрузи новое фото игрока в карточке участника')
        return f'Фото игрока #{pid}',old,row['photo_path']
    if kind == 'seat_layout':
        first=str(body.get('card_id') or '')
        second=str(value or '')
        if first==second:fail(422,'Выбери две разные карточки')
        a=c.execute('SELECT * FROM seats WHERE card_id=?',(first,)).fetchone()
        b=c.execute('SELECT * FROM seats WHERE card_id=?',(second,)).fetchone()
        if not a or not b:fail(422,'Карточка не найдена')
        before={first:[a['table_no'],a['box_no']],second:[b['table_no'],b['box_no']]}
        c.execute('UPDATE seats SET table_no=-1,box_no=-1 WHERE card_id=?',(first,))
        c.execute('UPDATE seats SET table_no=?,box_no=? WHERE card_id=?',(a['table_no'],a['box_no'],second))
        c.execute('UPDATE seats SET table_no=?,box_no=? WHERE card_id=?',(b['table_no'],b['box_no'],first))
        duplicate=c.execute('''SELECT team_id,table_no,COUNT(*) n FROM seats
                GROUP BY team_id,table_no HAVING n>1''').fetchone()
        if duplicate:fail(409,'Недопустимая пересадка: два игрока одной команды за одним столом')
        return 'Обмен местами двух карточек',before,{first:before[second],second:before[first]}
    if kind == 'seating_import':
        payload=value
        if not isinstance(payload,dict):fail(422,'Требуется JSON рассадки')
        count=integer(payload.get('team_count'),'team_count',10,13)
        document=payload.get('document')
        if not isinstance(document,dict):fail(422,'Требуется JSON с variants')
        try:
            teams,cards=validate_seating(document,count)
        except (ValueError,TypeError,KeyError) as exc:
            fail(422,str(exc))
        previous_count=c.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
        old_map={r['card_id']:(r['team_id'],r['player_id']) for r in c.execute('SELECT card_id,team_id,player_id FROM seats')}
        old_names={r['team_id']:r['display_name'] for r in c.execute('SELECT team_id,display_name FROM teams')}
        old_caps={r['team_id']:r['captain_player_id'] for r in c.execute('SELECT team_id,captain_player_id FROM teams')}
        for table in ('votes','secrets','stages','seats','teams'):
            c.execute(f'DELETE FROM {table}')
        for r in teams:
            tid=r['team_id']
            name=old_names.get(tid,r['original_name'])
            c.execute('INSERT INTO teams(team_id,original_name,display_name) VALUES (?,?,?)',(tid,r['original_name'],name))
            c.execute('INSERT INTO stages(team_id) VALUES (?)',(tid,))
        for r in cards:
            old=old_map.get(r['card_id'])
            pid=old[1] if old and old[0]==r['team_id'] else None
            c.execute('INSERT INTO seats(card_id,team_id,table_no,box_no,player_id) VALUES (?,?,?,?,?)',
                (r['card_id'],r['team_id'],r['table'],r['box'],pid))
        for tid,cap in old_caps.items():
            if cap is not None and c.execute('SELECT 1 FROM seats WHERE player_id=? AND team_id=?',(cap,tid)).fetchone():
                c.execute('UPDATE teams SET captain_player_id=? WHERE team_id=?',(cap,tid))
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('team_count',?)",(str(count),))
        return ('Полная замена схемы рассадки',
                {'teams':previous_count,'cards':len(old_map),'published_reset':True},
                {'teams':count,'cards':len(cards),'published_reset':True})
    if kind == 'vote_mode':
        old = c.execute("SELECT value FROM settings WHERE key='vote_mode'").fetchone()
        new=str(value or '')
        if new not in ('target','voter'):fail(422,'Режим голосования: target или voter')
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('vote_mode',?)",(new,))
        return 'Режим начисления голосов',old[0] if old else 'target',new
    if kind == 'vote':
        voter=team(c,body.get('team_id'))
        row=c.execute('SELECT target_team_id FROM votes WHERE voter_team_id=?',(voter,)).fetchone()
        old=row['target_team_id'] if row else None
        new=None if clear else team(c,value)
        if new==voter:fail(422,'Голосование за свою команду запрещено')
        if clear:
            c.execute('DELETE FROM votes WHERE voter_team_id=?',(voter,))
        else:
            c.execute('INSERT INTO votes(voter_team_id,target_team_id) VALUES (?,?) ON CONFLICT(voter_team_id) DO UPDATE SET target_team_id=excluded.target_team_id',(voter,new))
        return f'Голос команды №{voter}',old,new
    if kind == 'secret':
        slot=integer(body.get('slot'),'slot',1,3)
        row=c.execute('SELECT * FROM secrets WHERE slot=?',(slot,)).fetchone()
        old=dict(row) if row else None
        if clear:
            c.execute('DELETE FROM secrets WHERE slot=?',(slot,))
            return f'Secret Jack №{slot}',old,None
        pid=active_player(c,body.get('player_id'))
        confirmed=body.get('confirmed') is True
        killer_team=team(c,body.get('knockout_team_id')) if confirmed else None
        killer_id=active_player(c,body.get('knockout_player_id'),killer_team) if confirmed else None
        try:
            c.execute('INSERT INTO secrets(slot,player_id,knockout_team_id,knockout_player_id,confirmed) VALUES (?,?,?,?,?) ON CONFLICT(slot) DO UPDATE SET player_id=excluded.player_id,knockout_team_id=excluded.knockout_team_id,knockout_player_id=excluded.knockout_player_id,confirmed=excluded.confirmed',(slot,pid,killer_team,killer_id,int(confirmed)))
        except sqlite3.IntegrityError as e:
            fail(409,'Игрок уже назначен другим Secret Jack')
        return f'Secret Jack №{slot}',old,{'player_id':pid,'confirmed':confirmed,'knockout_team_id':killer_team,'knockout_player_id':killer_id}
    if kind=='winner':
        old = body.get('_winner_before')
        # Applied to published state by the caller (not a SQL table).
        return 'Решение по победителю',old,team(c,value) if not clear else None
    fail(422,'Неизвестный тип исправления')


def rebuild(c, p, green_snapshot, blue_snapshot, red_snapshot, final_snapshot, vote_snapshot):
    """Rebuild all dependent private snapshots from SQL with existing reveal steps."""
    p['team_count']=c.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
    teams=list(c.execute('SELECT * FROM teams ORDER BY team_id'))
    p['teams']={str(r['team_id']):r['display_name'] for r in teams}
    p['roster']={}
    for r in teams:
        p['roster'][str(r['team_id'])]=[x[0] for x in c.execute(
            'SELECT p.name FROM seats s JOIN players p ON p.id=s.player_id WHERE s.team_id=? ORDER BY s.table_no,s.box_no',(r['team_id'],))]
    if p.get('captains'):
        p['captains']=[]
        for r in teams:
            player=c.execute('SELECT id,name,photo_path FROM players WHERE id=?',(r['captain_player_id'],)).fetchone() if r['captain_player_id'] else None
            if player and not c.execute('SELECT 1 FROM seats WHERE player_id=? AND team_id=?',(player['id'],r['team_id'])).fetchone():
                player=None
                c.execute('UPDATE teams SET captain_player_id=NULL WHERE team_id=?',(r['team_id'],))
            p['captains'].append({'team_id':r['team_id'],'name':player['name'] if player else 'Капитан не выбран',
                                  'player_id':player['id'] if player else None,'has_photo':bool(player['photo_path']) if player else False})
    old_phases=list(p['published_phases'])
    old_revealed=list(p.get('revealed_slots',[]))
    old_votes=bool(p.get('votes_published'))
    old_final=bool(p.get('final_show'))
    stages={r['team_id']:r for r in c.execute('SELECT * FROM stages ORDER BY team_id')}
    for phase in list(p['published_phases']):
        if phase not in PHASES:
            p['published_phases'].remove(phase)
            continue
        missing=any(any(stages[t][field] is None for field in REQUIRED[phase]) for t in stages)
        if phase=='red' and not missing:
            positions=[stages[t]['red_place'] for t in stages]
            missing=sorted(positions)!=list(range(1,len(stages)+1))
        if missing:
            # Retract this and subsequent stages instead of showing fabricated 0 scores.
            p['published_phases']=list(PHASES[:PHASES.index(phase)])
            break
    p['stages']={}
    if p['published_phases']:
        rate_re=current_rate(c,'reentry')
        rate_add=current_rate(c,'addon')
        if 'green' in p['published_phases'] and rate_re is None: fail(409,'Нужен норматив reentry')
        if 'blue' in p['published_phases'] and rate_add is None: fail(409,'Нужен норматив addon')
        for tid,row in stages.items():
            record={}
            if 'green' in p['published_phases']:
                g=row['green_stack']; re=row['reentry_count']*rate_re
                record['green']=green_points(g,re)
                record['green_stack_actual']=g
            if 'blue' in p['published_phases']:
                b=row['blue_stack']; add=row['addon_count']*rate_add
                record['blue']=blue_points(row['green_stack'],b,add,row['survivors'])
            if 'red' in p['published_phases']:
                record['red']=red_points(row['red_place'],p['team_count'])
            p['stages'][str(tid)]=record
    for phase in PHASES:
        key=phase+'_show'
        if phase not in p['published_phases']:
            p.pop(key,None)
            continue
        if key in p:
            prior=p[key]['step']
            fresh={'green':green_snapshot,'blue':blue_snapshot,'red':red_snapshot}[phase](p)
            fresh['step']=min(prior,len(fresh['ranking'])+1)
            p[key]=fresh
    # Recalculate revealed secret identities and recipients from current SQL rows.
    revealed=p.get('revealed_slots',[])
    available={}
    for row in c.execute('''SELECT s.*,p.name,s2.team_id AS jack_team_id,
                            p.photo_path,k.name AS knockout_name FROM secrets s
                            JOIN seats s2 ON s2.player_id=s.player_id
                            JOIN players p ON p.id=s.player_id
                            LEFT JOIN players k ON k.id=s.knockout_player_id'''):
        available[row['slot']]={'slot':row['slot'],'player_id':row['player_id'],'name':row['name'],
            'jack_team_id':row['jack_team_id'],'knockout_team_id':row['knockout_team_id'],
            'knockout_player_id':row['knockout_player_id'],'knockout_name':row['knockout_name'],
            'confirmed':bool(row['confirmed']),'has_photo':bool(row['photo_path'])}
    if 'red' in old_phases and 'red' not in p['published_phases']:
        # A once-published RED has been withdrawn, so downstream bonuses
        # cannot remain public. Legacy shows without RED are left intact.
        p['revealed_slots']=[]
    else:
        # The director can only reveal 1, then 2, then 3.
        # If an already-revealed Jack is deleted, retract that reveal AND
        # the later ones. They remain editable drafts in the database and
        # can be deliberately re-revealed in order after correction.
        retained=[]
        for slot in (1,2,3):
            if slot in revealed and slot in available:
                retained.append(slot)
            else:
                break
        p['revealed_slots']=retained
    p['revealed_secrets']=[available[x] for x in p['revealed_slots']]
    if 'secret_show' in p:
        n=len(p['revealed_slots'])
        p['secret_show']['step']=min(p['secret_show']['step'],n+(1 if n==3 else 0))
    votes=[dict(r) for r in c.execute('SELECT voter_team_id,target_team_id FROM votes ORDER BY voter_team_id')]
    if p.get('votes_published') and (len(votes)!=p['team_count'] or len(p['revealed_slots'])<3 or 'red' not in p['published_phases']):
        # Incomplete ballots or withdrawn Secret Jack => no valid published vote score.
        p['votes_published']=False
        p['published_votes']=[]
        p.pop('vote_show',None)
    elif p.get('votes_published'):
        p['published_votes']=votes
    p['vote_mode']=(c.execute("SELECT value FROM settings WHERE key='vote_mode'").fetchone() or ['target'])[0]
    # Private authoritative full leaderboard, independent from the presentation step.
    p['ranking']=published_ranking(
        {int(k):v for k,v in p['teams'].items()},p['stages'],p['revealed_secrets'],
        p['published_votes'],p['revealed_slots'],p['votes_published'],p['vote_mode'],p['team_count'])
    if 'vote_show' in p:
        old_step=p['vote_show']['step']
        prematch=copy.deepcopy(p)
        prematch['ranking']=published_ranking(
            {int(k):v for k,v in p['teams'].items()},p['stages'],p['revealed_secrets'],
            [],p['revealed_slots'],False,p['vote_mode'],p['team_count'])
        prematch['votes_published']=False
        p['vote_show']=vote_snapshot(prematch,votes)
        p['vote_show']['step']=min(old_step,len(votes)+1)
    if 'final_show' in p:
        old_step=p['final_show']['step']
        if not p['votes_published'] or len(p['revealed_slots'])<3:
            p.pop('final_show',None)
        else:
            try:
                snapshot=final_snapshot(p)
            except HTTPException as exc:
                if exc.status_code!=409: raise
                p.pop('final_show',None)
                p['winner_decision']=None
            else:
                snapshot['step']=old_step
                p['final_show']=snapshot
    # Reconcile public media after a captain / Jack / photo correction.
    visible=set(p.get('visible_player_ids',[]))
    visible.update(x['player_id'] for x in p.get('captains',[]) if x.get('player_id'))
    visible.update(x['player_id'] for x in p['revealed_secrets'])
    valid={r['player_id']:r['photo_path'] for r in c.execute('SELECT id AS player_id, photo_path FROM players')}
    visible={x for x in visible if x in valid and c.execute('SELECT 1 FROM seats WHERE player_id=?',(x,)).fetchone()}
    p['visible_player_ids']=sorted(visible)
    p['visible_photos']={str(i):valid[i] for i in visible if valid[i]}
    if p['scene'] in ('green_show','blue_show','red_show') and p['scene'] not in p:
        p['scene']='pause'
    if p['scene']=='secret_show' and 'secret_show' not in p:
        p['scene']='pause'
    if p['scene']=='vote_show' and 'vote_show' not in p:
        p['scene']='pause'
    if p['scene']=='final_show' and 'final_show' not in p:
        p['scene']='pause'
    return {'retracted_phases':[x for x in old_phases if x not in p['published_phases']],
            'retracted_secrets':[x for x in old_revealed if x not in p['revealed_slots']],
            'votes_retracted':old_votes and not p['votes_published'],
            'final_retracted':old_final and not p.get('final_show'),
            'score_changes':[]}


def score_delta(old,new):
    old_map={r['team_id']:r for r in old.get('ranking',[])}
    changes=[]
    for r in new.get('ranking',[]):
        before=old_map.get(r['team_id'])
        if before and (before['total']!=r['total'] or before['place']!=r['place']):
            changes.append({'team_id':r['team_id'],'name':r['name'],
                            'old_total':before['total'],'new_total':r['total'],
                            'old_place':before['place'],'new_place':r['place']})
    return changes
