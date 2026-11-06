/* Protected corrections must be discoverable and enforce extra PIN confirmation. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const html=fs.readFileSync('sochi_show/static/admin.html','utf8');
const js=fs.readFileSync('sochi_show/static/protected-editor.js','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.js','utf8');
const py=fs.readFileSync('sochi_show/server.py','utf8');
const engine=fs.readFileSync('sochi_show/corrections.py','utf8');
const css=fs.readFileSync('sochi_show/static/protected-editor.css','utf8');
for(const id of ['protected-editor-panel','protected-kind','protected-fields',
                 'protected-preview','protected-result','protected-confirm',
                 'protected-reason','protected-pin','protected-phrase',
                 'protected-history-btn']){
  assert.ok(html.includes('id="'+id+'"'),'missing correction control '+id);
}
for(const kind of ['stage','chip_rate','team_name','captain','player_name',
                   'seat','seat_layout','seating_import','photo','secret',
                   'vote','vote_mode','winner']){
  assert.ok(html.includes('value="'+kind+'"'),'missing editor action '+kind);
}
assert.match(js,/api\('\/sochi\/api\/admin\/correction\/preview'/);
assert.match(js,/api\('\/sochi\/api\/admin\/correction\/apply'/);
assert.match(js,/expected_version:state\.publication_version/);
assert.match(js,/\bpin,reason,confirm:confirmText/);
assert.match(js,/sochi-admin-refreshed/);
assert.match(admin,/dispatchEvent\(new Event\('sochi-admin-refreshed'\)\)/);
assert.match(js,/retracted_phases/);
assert.match(js,/votes_retracted/);
assert.match(js,/retracted_secrets/);
assert.match(py,/def check_correction_version/);
assert.match(py,/secrets\.compare_digest\(pin,password\)/);
assert.match(py,/body\.get\('confirm'\)!='ИСПРАВИТЬ'/);
assert.match(py,/correction_history/);
assert.match(engine,/def rebuild\(/);
assert.match(engine,/red_points/);
assert.match(engine,/blue_points/);
assert.match(css,/protected-compare-grid/);
console.log('PROTECTED EDITOR UI PASS: PIN, version, public-rank preview, every edit kind and full audit');
