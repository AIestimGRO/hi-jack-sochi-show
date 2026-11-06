/* Cinematic CAPTAINS scene must replace the old black card grid on TV.
   All names and photos must originate only from published public state. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context={window:{},Intl};
for(const name of ['jack-sword-motion','green-show','captain-show']){
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+name+'.js','utf8'),context);
}
const {demo,render}=context.window.CaptainShow;
const host={className:'',innerHTML:''};
const cabin=html=>{
  const match=html.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(match,'mountain route contains a cable car');
  return match[0];
};
for(const count of [10,11]){
  for(const all of [false,true]){
    const state=demo(count,all);
    render(host,state);
    assert.equal(host.className,'scene green-show-stage captain-show-stage');
    assert.match(host.innerHTML,/КАПИТАНЫ <em>ЭКСПЕДИЦИЙ<\/em>/);
    assert.match(host.innerHTML,/EXPEDITION \/ CAPTAINS/);
    assert.match(host.innerHTML,/gs-jack-animation-image/);
    assert.match(host.innerHTML,/data:image\/gif;base64,/);
    assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
    assert.equal((host.innerHTML.match(/class="cs-tile /g)||[]).length,count);
    assert.equal((host.innerHTML.match(/cs-team-name/g)||[]).length,count);
    assert.equal((host.innerHTML.match(/class="cs-assigned"/g)||[]).length,0);
    const assignedCount=all?count:2;
    assert.equal((host.innerHTML.match(/class="cs-tile cs-assigned"/g)||[]).length,assignedCount);
    assert.equal((host.innerHTML.match(/class="cs-tile cs-awaiting"/g)||[]).length,count-assignedCount);
    assert.equal((host.innerHTML.match(/КАПИТАН ОЖИДАЕТСЯ/g)||[]).length,count-assignedCount);
    assert.doesNotMatch(host.innerHTML,/Капитан не выбран/,'avoid huge placeholder name');
    assert.match(host.innerHTML,/Чуйка VS Диапазоны/);
    assert.match(host.innerHTML,/All-in и подомам/);
    if(count===11){
      assert.match(host.innerHTML,/Fuck дилеру/);
      assert.match(host.innerHTML,/--captain-columns:6/);
    }else{
      assert.doesNotMatch(host.innerHTML,/Fuck дилеру/);
      assert.match(host.innerHTML,/--captain-columns:5/);
    }
    const matchingBlue=context.window.GreenShow.alpineArt('blue');
    assert.equal(cabin(host.innerHTML),cabin(matchingBlue),'cabin stays at BLUE for captains, never RED');
    const visibleIds=[...host.innerHTML.matchAll(/ЭКСПЕДИЦИЯ (\d\d)/g)].map(m=>Number(m[1]));
    assert.deepEqual(visibleIds,Array.from({length:count},(_,i)=>i+1));
  }
}
// Uploaded captain portrait is displayed for a published ID; an unassigned
// team never fetches a photo or exposes a draft captain.
const state=demo(10,false);
state.captains[0].player_id=1007;
state.captains[0].has_photo=true;
state.teams[1]='Команда <script>danger</script>';
render(host,state);
assert.match(host.innerHTML,/\/sochi\/api\/public\/photo\/1007/);
assert.doesNotMatch(host.innerHTML,/<script>danger<\/script>/);
assert.match(host.innerHTML,/&lt;script&gt;danger&lt;\/script&gt;/);
assert.equal((host.innerHTML.match(/\/sochi\/api\/public\/photo\//g)||[]).length,1);

const screen=fs.readFileSync('sochi_show/static/screen.js','utf8');
const screenHTML=fs.readFileSync('sochi_show/static/screen.html','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.html','utf8');
const preview=fs.readFileSync('sochi_show/static/captain-preview.html','utf8');
const css=fs.readFileSync('sochi_show/static/captain-show.css','utf8');
assert.match(screen,/window.CaptainShow.render\(panel,/);
assert.match(screen,/\['green_show','blue_show','red_show','secret_show','vote_show','final_show','captains'\]/);
assert.doesNotMatch(screen,/panel.innerHTML=header\('КАПИТАНЫ'\)/);
assert.match(screenHTML,/captain-show.js\?v=captains-v1/);
assert.match(screenHTML,/captain-show.css\?v=captains-v1/);
assert.match(admin,/Демо капитанов/);
assert.match(preview,/ДЕМО КАПИТАНОВ · НЕ ЭФИР/);
assert.match(css,/cs-tile/);
console.log('CAPTAINS visual PASS: 10/11 teams, 2/all assigned, no ugly placeholder, BLUE cabin, animated Jack');
