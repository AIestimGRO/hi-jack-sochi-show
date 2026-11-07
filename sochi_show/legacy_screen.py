"""JavaScript-free television screen for projectors with outdated WebView engines.

Only render the already-sanitized public_safe state. Never access raw admin state.
The browser automatically reloads the page every 5 seconds using standard HTML.
"""
from html import escape


def e(value):
    return escape(str(value if value is not None else ''), quote=True)


def board_row(position, name, info=''):
    return ('<div class="rank-row"><span class="rank-number">' + e(position) +
            '</span><span class="rank-name">' + e(name) +
            '</span><span class="rank-info">' + e(info) + '</span></div>')


def render_legacy_screen(state):
    scene = state.get('scene', 'intro')
    phases = state.get('published_phases') or []
    mode = (state.get('blue_policy') or {}).get('mode')
    final_table = mode == 'final_table'
    names = state.get('teams') or {}
    lines = []
    headline = 'HI, JACK — HI, SOCHI'
    subheading = '7 НОЯБРЯ 2026 · ПРЯМОЙ ЭФИР'
    note = 'СЛЕДУЮЩИЙ ЭТАП СКОРО НАЧНЁТСЯ'

    if scene in ('teams', 'captains'):
        headline = 'КОМАНДЫ ТУРНИРА' if scene == 'teams' else 'КАПИТАНЫ ФИНАЛА'
        if scene == 'teams':
            counts = state.get('team_reentries') or {}
            captains = state.get('team_captains') or {}
            ordered = sorted(names, key=lambda ident: (int(counts.get(str(ident), 0)), int(ident)))
            for place, ident in enumerate(ordered, 1):
                captain = captains.get(str(ident))
                caption = names[ident] + (' · КАПИТАН: ' + captain if captain else '')
                lines.append(board_row('#' + str(place), caption,
                                       'КОМАНДА ' + str(ident) + ' · RE-ENTRY: ' +
                                       str(int(counts.get(str(ident), 0)))))
        else:
            for captain in state.get('captains') or []:
                lines.append(board_row('#' + str(captain.get('team_id', '')),
                                       captain.get('name', ''),
                                       names.get(str(captain.get('team_id', '')), '')))
        note = 'HI, JACK — HI, SOCHI'
    elif scene in ('green_show', 'blue_show', 'red_show'):
        phase = scene.split('_')[0].upper()
        view = state.get(phase.lower() + '_view') or {}
        headline = 'РЕЗУЛЬТАТЫ ' + phase
        note = ('РАСКРЫТО: ' + str(len(view.get('revealed') or [])) + ' / ' +
                str(view.get('count', state.get('team_count', 0))))
        for item in view.get('revealed') or []:
            place = item.get('place', '—')
            if phase == 'RED' and final_table:
                info = 'ФИНИШ RED №' + str(item.get('red_place', place))
            elif phase == 'GREEN':
                info = str(item.get('green', item.get('total', ''))) + ' фишек'
            elif phase == 'BLUE':
                info = str(item.get('chip_net', item.get('blue', ''))) + ' фишек'
            else:
                info = str(item.get('total', '')) + ' очков'
            lines.append(board_row('#' + str(place), item.get('name', ''), info))
    elif scene == 'secret_show':
        view = state.get('secret_view') or {}
        headline = 'SECRET JACK · РАСКРЫТИЕ'
        for item in view.get('revealed') or []:
            lines.append(board_row('#' + str(item.get('slot', '')),
                                   item.get('name', ''),
                                   'ВЫБИТ' if item.get('confirmed') else 'В ИГРЕ'))
        note = 'РАСКРЫТО: ' + str(len(view.get('revealed') or [])) + ' / 3'
    elif scene == 'vote_show':
        view = state.get('vote_view') or {}
        headline = 'ГОЛОСА КАПИТАНОВ'
        note = 'РАСКРЫТО: ' + str(len(view.get('revealed') or [])) + ' / ' + str(view.get('count', 0))
        for item in view.get('revealed') or []:
            target = item.get('receiver_team_id', item.get('target_team_id'))
            lines.append(board_row('♠', names.get(str(target), 'Команда ' + str(target)),
                                   '+10 000 фишек' if final_table else '+10 000 очков'))
    elif scene == 'final_show':
        view = state.get('final_view') or {}
        step = view.get('step', 0)
        headline = 'ФИНАЛЬНОЕ НАГРАЖДЕНИЕ'
        note = 'ПОБЕДИТЕЛЬ ОПРЕДЕЛЁН ФИНАЛЬНЫМ СТОЛОМ RED' if final_table else 'ИТОГИ ТУРНИРА'
        if step == 5 and view.get('champion'):
            champ = view['champion']
            headline = 'ПОБЕДИТЕЛЬ ТУРНИРА'
            lines.append(board_row('★', champ.get('name', ''), '1 МЕСТО'))
        elif step >= 4:
            for item in view.get('board') or []:
                lines.append(board_row('#' + str(item.get('place', '')), item.get('name', ''), ''))
        else:
            for item in view.get('revealed') or []:
                lines.append(board_row('#' + str(item.get('ceremony_place', '')), item.get('name', ''), ''))
    elif scene in ('green', 'blue', 'red', 'final', 'winner', 'secrets', 'votes'):
        headline = {'green':'GREEN', 'blue':'BLUE', 'red':'RED · ФИНАЛЬНЫЙ СТОЛ',
                    'final':'ИТОГИ ТУРНИРА', 'winner':'ПОБЕДИТЕЛЬ ТУРНИРА',
                    'secrets':'SECRET JACK', 'votes':'ГОЛОСА КАПИТАНОВ'}[scene]
        ranking = state.get('ranking') or []
        if scene == 'winner' and ranking:
            winner = next((r for r in ranking if r.get('place') == 1), ranking[0])
            lines.append(board_row('★', winner.get('name', ''), 'ПОБЕДИТЕЛЬ RED' if final_table else 'ПОБЕДИТЕЛЬ'))
        else:
            for item in ranking:
                info = 'МЕСТО RED №' + str(item.get('red_place')) if final_table and 'red' in phases else str(item.get('total', '')) + ' очков'
                lines.append(board_row('#' + str(item.get('place', '')), item.get('name', ''), info))
        note = 'ОФИЦИАЛЬНЫЙ РЕЙТИНГ'
    elif scene == 'pause':
        headline = 'ПАУЗА'
        note = 'СКОРО ПРОДОЛЖИМ'

    if not lines:
        lines.append('<div class="standby">РЕЗУЛЬТАТЫ ПОКА СКРЫТЫ</div>')
    rows = ''.join(lines)

    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="5">'
        '<meta name="referrer" content="no-referrer">'
        '<title>HI, JACK — HI, SOCHI · ЭКРАН ДЛЯ ПРОЕКТОРА</title>'
        '<style>'
        'html,body{margin:0;min-height:100%;background:#051c22;color:#f4e5d1;'
        'font-family:Arial,Helvetica,sans-serif;overflow-x:hidden}'
        'body{background:radial-gradient(ellipse at 70% 14%,#276477 0%,#08282e 45%,#051c22 94%)}'
        '.wrap{box-sizing:border-box;width:100%;min-height:100vh;padding:3vh 5vw 3vh;text-align:center}'
        '.mast{color:#c8a36f;font-weight:bold;letter-spacing:.35em;font-size:22px;font-size:2vw}'
        '.brand{font-size:44px;font-size:3.1vw;color:#e5c18f;font-weight:900;margin:1vh auto}'
        '.brand em{font-style:normal;color:#a4d7e5}'
        '.line{height:3px;max-width:1000px;margin:2vh auto;background:#94785a}'
        'h1{font-size:48px;font-size:3.7vw;margin:2vh 0;text-transform:uppercase;letter-spacing:.05em}'
        '.board{max-width:1450px;margin:1vh auto;max-height:69vh;overflow:hidden}'
        '.rank-row{box-sizing:border-box;display:table;table-layout:fixed;width:100%;'
        'margin:0 0 .6vh;padding:1.1vh 1.5vw;background:#10383f;'
        'border:1px solid #42717a;border-radius:9px;text-align:left;font-size:23px;font-size:1.65vw}'
        '.rank-row span{display:table-cell;vertical-align:middle}'
        '.rank-number{width:10%;font-weight:bold;color:#e6b874}'
        '.rank-name{width:62%;font-weight:bold;color:#fff1dc}'
        '.rank-info{width:28%;text-align:right;color:#bcdde6}'
        '.standby{margin:9vh auto;font-size:29px;color:#e5c18f;letter-spacing:.2em}'
        '.note{margin:2vh auto;font-weight:bold;font-size:20px;letter-spacing:.1em;color:#e4c793}'
        '.footer{font-size:15px;margin:2vh;color:#95b0b4}'
        '</style></head><body><div class="wrap">'
        '<div class="mast">HI, JACK CLUB · 07.11.2026</div>'
        '<div class="brand">HI, JACK <em>— HI, SOCHI</em></div>'
        '<div class="line"></div><h1>' + e(headline) + '</h1>'
        '<div class="board">' + rows + '</div>'
        '<div class="note">' + e(note) + '</div>'
        '<div class="footer">● ЭФИР · РЕЖИМ СОВМЕСТИМОСТИ · ОБНОВЛЕНИЕ КАЖДЫЕ 5 СЕКУНД</div>'
        '</div></body></html>'
    )
