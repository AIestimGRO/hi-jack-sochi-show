/* BLUE->points controller wiring: no GREEN+BLUE double count, and bonus is separate. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync('sochi_show/static/admin.html','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.js','utf8');
const blue=fs.readFileSync('sochi_show/static/blue-points-admin.js','utf8');
const projector=fs.readFileSync('sochi_show/static/blue-show.js','utf8');
const server=fs.readFileSync('sochi_show/server.py','utf8');
const core=fs.readFileSync('sochi_show/core.py','utf8');
for(const name of ['blue-points-panel','bp-mode','bp-preview','bp-confirm','bp-reveal',
  'bp-points-table','bp-reason','bp-pin','chips-per-entry']){
 assert.match(html,new RegExp('id="'+name+'"'),'missing BLUE director field '+name);
}
assert.match(html,/чистым фишкам BLUE/);
assert.match(html,/Лучшая команда — ровно 1 000 000, последняя — ровно 100 000/);
assert.match(html,/5 000 на каждого/);
assert.match(blue,/net:r\.blue_net_chips/);
assert.match(blue,/survivors:r\.survivor_bonus\|\|0/);
assert.match(blue,/900000\*\(r\.net-lo\)/);
assert.match(blue,/correction\/preview/);
assert.match(blue,/correction\/apply/);
assert.match(blue,/blue-policy-reveal/);
assert.match(blue,/state\.publication_version/);
assert.match(blue,/confirm:'ИСПРАВИТЬ'/);
assert.match(server,/entry_rate is None/);
assert.match(server,/r\['blue_stack'\] - initial_entries - r\['reentry_chips'\] - r\['addon_chips'\]/);
assert.match(server,/survivor_bonus.*5000 \* r\['survivors'\]/);
assert.match(core,/chip_net = entry\.get\('blue_net_chips', g \+ b\)/);
assert.match(core,/award = converted \+ survivor_bonus/);
assert.match(projector,/БОНУС ЗА ВЫЖИВШИХ · ОТДЕЛЬНО/);
assert.match(admin,/Сначала сохрани стоимость ВХОДА одного игрока/);
console.log('BLUE FINAL TABLE UI PASS: net chips, 100k–1m scaling, 5k separate survivor, PIN and on-air reveal');
