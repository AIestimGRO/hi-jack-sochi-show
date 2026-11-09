"""Premium no-JavaScript Wanbo broadcast, rendered on the server as PNG.

Only call this with an already sanitized public_safe() state.
The projector uses an ordinary IMG and an HTML meta refresh. No ES syntax,
WebSocket, animation APIs or client-side JS are required.
"""
from __future__ import annotations

import io
import json
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900
CREAM = (253, 237, 214)
GOLD = (241, 182, 123)
MUTED = (179, 207, 204)
WHITE = (255, 248, 237)


def _font(size=25, bold=False):
    path = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _text(draw, xy, value, font, fill=CREAM, anchor=None):
    if value is None:
        return
    text = str(value)
    if anchor:
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)
    else:
        draw.text(xy, text, font=font, fill=fill)


def _trim(value, limit=30):
    text = str(value or "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _fmt(value):
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _art(draw):
    # Dark seawater gradient, alpenglow and a deep theatre-like background.
    for y in range(H):
        amount = y / H
        draw.line((0, y, W, y),
                  fill=(int(15 + 15 * amount), int(48 - 20 * amount),
                        int(55 - 17 * amount)))
    draw.ellipse((930, -140, 1740, 645), fill=(55, 55, 61))
    draw.ellipse((1010, -90, 1680, 540), fill=(76, 72, 71))
    draw.polygon([(0, 755), (195, 520), (330, 625), (490, 360),
                  (650, 590), (800, 325), (965, 560), (1170, 175),
                  (1400, 540), (1560, 340), (W, 505), (W, H),
                  (0, H)], fill=(44, 65, 67))
    draw.polygon([(0, 850), (180, 700), (340, 760), (510, 590),
                  (700, 710), (950, 490), (1250, 730), (1460, 570),
                  (W, 665), (W, H), (0, H)], fill=(28, 47, 53))
    draw.polygon([(1104, 280), (1170, 175), (1250, 313),
                  (1194, 280), (1170, 229), (1148, 283)],
                 fill=(175, 162, 157))
    draw.polygon([(757, 387), (800, 325), (849, 423), (819, 398),
                  (800, 363), (784, 400)], fill=(137, 137, 139))
    # One cable, four waypoints and a bronze-gold Hi Jack gondola.
    draw.line((485, 752, 1415, 186), fill=(25, 35, 41), width=10)
    draw.line((485, 752, 1415, 186), fill=(193, 161, 125), width=3)
    for x, y in [(485, 752), (748, 592), (1038, 415), (1415, 186)]:
        draw.ellipse((x-10, y-10, x+10, y+10), fill=GOLD, outline=(50, 54, 56), width=4)
    gx, gy = 1050, 406
    draw.line((gx, gy, gx, gy+55), fill=GOLD, width=5)
    draw.rounded_rectangle((gx-55, gy+54, gx+55, gy+118),
                           radius=10, fill=(122, 55, 75), outline=GOLD, width=4)
    draw.rounded_rectangle((gx-41, gy+65, gx-7, gy+94),
                           radius=4, fill=(133, 191, 193), outline=CREAM, width=2)
    draw.rounded_rectangle((gx+7, gy+65, gx+41, gy+94),
                           radius=4, fill=(133, 191, 193), outline=CREAM, width=2)
    # Deco corner strokes and title ribbon.
    draw.line((52, 131, 1548, 131), fill=(111, 116, 115), width=2)
    draw.line((54, 838, 1546, 838), fill=(125, 115, 100), width=2)
    draw.rounded_rectangle((1270, 34, 1540, 100), radius=32,
                           fill=(100, 62, 77), outline=(204, 168, 128), width=2)
    _text(draw, (1303, 52), "STAGE  /  HI, JACK", _font(22, True), WHITE)
    # Suit emblem for old clients that cannot render animated transparent GIFs.
    draw.rounded_rectangle((1406, 145, 1516, 256), radius=19,
                           fill=(67, 47, 52), outline=GOLD, width=4)
    _text(draw, (1431, 152), "♠", _font(73, True), GOLD)


def _rows(state):
    scene = state.get("scene", "intro")
    names = state.get("teams") or {}
    revealed = []
    if scene == "teams":
        counts = state.get("team_reentries") or {}
        captains = state.get("team_captains") or {}
        ordered = sorted(names, key=lambda key: (int(counts.get(str(key), 0)), int(key)))
        return [(_trim(names[key], 26),
                 ("КАПИТАН  " + _trim(captains.get(str(key)), 16) + "   ·   "
                  if captains.get(str(key)) else "") +
                 "RE-ENTRY  " + str(counts.get(str(key), 0)))
                for key in ordered]
    if scene == "captains":
        return [(_trim(r.get("name", ""), 27),
                 _trim(names.get(str(r.get("team_id")), ""), 32))
                for r in state.get("captains") or []]
    if scene in ("green_show", "blue_show", "red_show"):
        phase = scene.replace("_show", "")
        visible = (state.get(phase + "_view") or {}).get("revealed") or []
        for row in visible:
            if scene == "red_show":
                note = "МЕСТО RED  #" + str(row.get("red_place", row.get("place", "—")))
            elif scene == "blue_show":
                note = "ЧИСТЫЕ ФИШКИ  " + _fmt(row.get("chip_net", row.get("total")))
            else:
                note = "GREEN  " + _fmt(row.get("green"))
            revealed.append((_trim(row.get("name", ""), 29), note))
        return revealed
    if scene == "secret_show":
        for row in (state.get("secret_view") or {}).get("revealed") or []:
            note = ("ВЫБИТ  ·  БОНУС НАЧИСЛЕН" if row.get("confirmed")
                    else "НЕ ВЫБИТ  ·  БОНУС 0")
            revealed.append((_trim(row.get("name"), 28), note))
        return revealed
    if scene == "vote_show":
        for row in (state.get("vote_view") or {}).get("revealed") or []:
            receiver = row.get("receiver_name") or names.get(str(row.get("receiver_team_id")), "")
            revealed.append((_trim(receiver, 28),
                             "ГОЛОС  +" + _fmt(row.get("points", 0)) + " ФИШЕК"))
        return revealed
    if scene == "final_show":
        view = state.get("final_view") or {}
        if view.get("board"):
            return [(_trim(r.get("name", ""), 29), "МЕСТО  #" + str(r.get("place", "—")))
                    for r in view["board"]]
        return [(_trim(r.get("name", ""), 29), "ФИНАЛЬНОЕ МЕСТО")
                for r in view.get("revealed") or []]
    if scene in ("green", "blue", "red", "final", "winner", "votes", "secrets"):
        return [(_trim(r.get("name", ""), 29), "МЕСТО  #" + str(r.get("place", "—")))
                for r in state.get("ranking") or []]
    return []


def _copy(state, draw):
    scene = state.get("scene", "intro")
    labels = {
        "intro": ("HI, SOCHI", "ДОРОГА К ВЕРШИНЕ", "ТРИ ЭТАПА. ОДНА ВЕРШИНА."),
        "pause": ("ПАУЗА", "СКОРО ПРОДОЛЖИМ", "HI, JACK — HI, SOCHI"),
        "teams": ("НАШИ", "КОМАНДЫ", "МЕНЬШЕ RE-ENTRY — ВЫШЕ В СПИСКЕ"),
        "captains": ("КАПИТАНЫ", "ФИНАЛЬНОГО СТОЛА", "ЛИДЕРЫ КОМАНД"),
        "green_show": ("ЭТАП 01", "GREEN", "РАСКРЫВАЕМ МЕСТА"),
        "blue_show": ("ЭТАП 02", "BLUE", "ЧИСТЫЕ ФИШКИ И МЕСТА"),
        "red_show": ("ФИНАЛЬНЫЙ", "ШТУРМ", "МЕСТА RED РАСКРЫВАЮТСЯ"),
        "secret_show": ("ТАЙНЫЙ", "JACK", "РАСКРЫТИЕ ТРЁХ ВАЛЕТОВ"),
        "vote_show": ("ГОЛОСА", "КАПИТАНОВ", "ТАЙНОЕ ГОЛОСОВАНИЕ"),
        "final_show": ("ЛЕГЕНДЫ", "ФИНАЛА", "НА ПУТИ К ЧЕМПИОНУ"),
        "winner": ("ЧЕМПИОН", "HI, SOCHI", "ПЕРВОЕ МЕСТО RED"),
    }
    first, second, caption = labels.get(scene, ("HI, JACK", scene.upper(), "ТУРНИРНЫЙ ЭФИР"))
    _text(draw, (55, 36), "♠  HI, JACK  —  HI, SOCHI", _font(42, True), CREAM)
    _text(draw, (58, 93), "HI, JACK CLUB   ·   LIVE BROADCAST", _font(19, True), GOLD)
    _text(draw, (63, 187), first, _font(56, True), CREAM)
    _text(draw, (63, 269), second, _font(64, True), GOLD)
    draw.line((65, 366, 590, 366), fill=GOLD, width=4)
    _text(draw, (65, 392), caption, _font(23, True), WHITE)
    _text(draw, (62, 855), "ЗАЛЕТАЙ   ·   ЗАЦЕПИСЬ   ·   ЗАВОЮЙ", _font(21, True), CREAM)
    _text(draw, (1145, 852), "WANBO  /  AUTO REFRESH", _font(16, True), MUTED)


def _scoreboard(draw, items, state):
    scene = state.get("scene")
    # A strong contrasting frame keeps every row legible on lower-end TVs.
    x, y, right, bottom = 758, 192, 1544, 817
    draw.rounded_rectangle((x, y, right, bottom), radius=24,
                           fill=(16, 34, 43), outline=(204, 155, 110), width=3)
    title = "КОМАНДЫ" if scene == "teams" else "РЕЗУЛЬТАТЫ / LIVE"
    _text(draw, (x+30, y+22), title, _font(25, True), GOLD)
    draw.line((x+30, y+64, right-30, y+64), fill=(94, 121, 119), width=2)
    count = min(len(items), 12)
    if not count:
        _text(draw, (x+39, y+122), "РЕЗУЛЬТАТЫ ЕЩЁ НЕ ОТКРЫТЫ", _font(23, True), CREAM)
        _text(draw, (x+39, y+172), "ОЖИДАЕМ КОМАНДУ ОРГАНИЗАТОРА", _font(17, True), MUTED)
        return
    row_h = min(64, int((bottom-y-90)/count))
    for idx, (main, subtitle) in enumerate(items[:count]):
        row_y = y + 75 + idx * row_h
        if idx % 2 == 0:
            draw.rounded_rectangle((x+17, row_y-2, right-17, row_y+row_h-4),
                                   radius=9, fill=(27, 52, 58))
        _text(draw, (x+31, row_y+3), str(idx+1).zfill(2),
              _font(20, True), GOLD)
        _text(draw, (x+90, row_y-1), main, _font(23 if count < 10 else 20, True), WHITE)
        _text(draw, (x+91, row_y+29), _trim(subtitle, 53),
              _font(14 if count > 9 else 16), MUTED)


def _cached_frame(state):
    image = Image.new("RGB", (W, H), (17, 42, 49))
    draw = ImageDraw.Draw(image)
    _art(draw)
    _copy(state, draw)
    _scoreboard(draw, _rows(state), state)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


@lru_cache(maxsize=12)
def render_png(sanitized_json):
    """Memoized by the public-safe published-state JSON, never raw admin data."""
    state = json.loads(sanitized_json)
    return _cached_frame(state)
