/* SECRET JACK projector smoke tests: one revealed identity per step and no extra bonuses. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const ctx={window:{},Intl};
for(const name of ['jack-sword-motion','green-show','secret-show']){
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+name+'.js','utf8'),ctx);
}
const {demo,frame,render}=ctx.window.SecretShow;
const data=demo(),host={className:'',innerHTML:''};
assert.equal(data.all_demo_cards.length,3);
assert.equal(data.all_demo_cards.filter(s=>s.confirmed).length,2);
const cabin=s=>{
  const m=s.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(m,'single gondola at RED summit');
  return m[0];
};
render(host,frame(data,0));
const fixedCabin=cabin(host.innerHTML);
assert.match(host.innerHTML,/SECRET JACK \/ 03/);
assert.match(host.innerHTML,/gs-jack-animation-image/);
assert.match(host.innerHTML,/data:image\/gif;base64,/);
assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
assert.doesNotMatch(host.innerHTML,/Демо-игрок А|Демо-игрок В|Демо-игрок Г/,'intro does not reveal roles');
assert.equal((host.innerHTML.match(/class="ss-seal ss-locked"/g)||[]).length,3);

for(const step of [1,2,3]){
  render(host,frame(data,step));
  assert.equal(cabin(host.innerHTML),fixedCabin,'show step does not move RED cabin');
  assert.equal((host.innerHTML.match(/ss-photo-frame/g)||[]).length,1);
  assert.match(host.innerHTML,/ss-player-name/);
  assert.match(host.innerHTML,/gs-jack-animation-image/);
  assert.ok(host.innerHTML.includes(data.all_demo_cards[step-1].name));
  for(const stillSecret of data.all_demo_cards.slice(step)){
    assert.ok(!host.innerHTML.includes(stillSecret.name),'upcoming names remain hidden');
  }
  if(step===2){
    assert.match(host.innerHTML,/SECRET JACK ВЫСТОЯЛ/);
    assert.match(host.innerHTML,/БОНУС НЕ НАЧИСЛЕН/);
    assert.doesNotMatch(host.innerHTML,/class="ss-result-block bounty"/);
  }else{
    assert.match(host.innerHTML,/\+10[\s\u00a0\u202f]000 ОЧКОВ/);
    assert.match(host.innerHTML,/class="ss-result-block bounty"/);
    assert.match(host.innerHTML,/ВЫБИЛ:/);
  }
}
render(host,frame(data,4));
assert.equal(cabin(host.innerHTML),fixedCabin);
assert.equal((host.innerHTML.match(/class="ss-summary-card"/g)||[]).length,3);
for(const secret of data.all_demo_cards)assert.ok(host.innerHTML.includes(secret.name));
assert.match(host.innerHTML,/ВСЕГО БОНУСОВ: 20.000|ВСЕГО БОНУСОВ: 20 000|ВСЕГО БОНУСОВ: 20 000/);
assert.match(host.innerHTML,/ДАЛЬШЕ — ГОЛОСОВАНИЕ КАПИТАНОВ/);

// An existing portrait remains private until its own role is published.
const mock=frame(data,1);
mock.revealed[0].has_photo=true;
render(host,mock);
assert.match(host.innerHTML,/\/sochi\/api\/public\/photo\/101/);
assert.doesNotMatch(host.innerHTML,/\/sochi\/api\/public\/photo\/102/);

const red=fs.readFileSync('sochi_show/static/red-show.js','utf8');
assert.doesNotMatch(red,/rs-hero-rank-badge/,'remove RED caption below place changes');
assert.doesNotMatch(red,/const label=place/,'unused title helper removed');
const screen=fs.readFileSync('sochi_show/static/screen.js','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.js','utf8');
const stage=fs.readFileSync('sochi_show/static/screen.html','utf8');
const controls=fs.readFileSync('sochi_show/static/admin.html','utf8');
const preview=fs.readFileSync('sochi_show/static/secret-preview.html','utf8');
assert.match(screen,/scene==='secret_show'/);
assert.match(screen,/\['green_show','blue_show','red_show','secret_show','vote_show','final_show','captains'\]/);
assert.match(stage,/secret-show\.css/);
assert.match(stage,/secret-show\.js/);
assert.match(controls,/id="secret-show-start"/);
assert.match(controls,/id="secret-show-back"/);
assert.match(controls,/id="secret-show-next"/);
assert.match(admin,/renderSecretDirector\(\)/);
assert.match(admin,/action:'secret-show-step'/);
assert.match(preview,/ДЕМО SECRET JACK · НЕ ЭФИР/);
console.log('SECRET JACK visuals PASS: no RED labels, 3 private reveals, surviving Jack, bonus summary and permanent animation');
