/* Visual and math smoke tests: RED ranking and stable SUMMIT cabin. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const ctx={window:{},Intl};
for(const file of ['rank-mascots','jack-sword-motion','green-show','blue-show','red-show']){
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+file+'.js','utf8'),ctx);
}
const {demo,frame,render}=ctx.window.RedShow;
const getCabin=s=>{
  const match=s.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(match,'a single cable car exists');
  return match[0];
};
const host={className:'',innerHTML:''};

for(const count of [10,11]){
  const set=demo(count);
  assert.equal(set.max_step,count+1);
  assert.equal(set.demo_ranking.length,count);
  const blue=ctx.window.BlueShow.demo(count).demo_ranking;
  const byID=new Map(blue.map(r=>[r.team_id,r]));
  const expectedRedPlaces=Array.from(set.demo_ranking, r=>r.red_place).sort((a,b)=>a-b);
  assert.deepEqual(expectedRedPlaces,Array.from({length:count},(_,i)=>i+1));
  set.demo_ranking.forEach(r=>{
    assert.equal(r.total,byID.get(r.team_id).total+r.red,'cumulative total');
    assert.equal(r.red,130000-(r.red_place-1)*10000,'RED existing fixed formula');
    assert.equal(r.move,r.blue_place-r.place);
  });
  const blueHost={};
  ctx.window.BlueShow.render(blueHost,ctx.window.BlueShow.frame(ctx.window.BlueShow.demo(count),0));
  const blueCabin=getCabin(blueHost.innerHTML);

  render(host,frame(set,0));
  const redCabin=getCabin(host.innerHTML);
  assert.notEqual(redCabin,blueCabin,'cable advances to RED only at stage change');
  assert.match(host.innerHTML,/STAGE 03 \/ RED/);
  assert.match(host.innerHTML,/GREEN ✓/);
  assert.match(host.innerHTML,/BLUE ✓/);
  assert.match(host.innerHTML,/RED ✓/);
  assert.match(host.innerHTML,/gs-jack-animation-image/);
  assert.match(host.innerHTML,/data:image\/gif;base64,/);
  assert.doesNotMatch(host.innerHTML,/rs-hero-name/,'intro has no published teams');
  assert.doesNotMatch(host.innerHTML,/rs-list-row/,'intro hides rankings');
  assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
  for(const step of [1,Math.ceil(count/2),count,count+1]){
    render(host,frame(set,step));
    assert.equal(getCabin(host.innerHTML),redCabin,'no cabin movement on rank clicks');
    assert.match(host.innerHTML,/gs-jack-animation-image/);
  }
  render(host,frame(set,1));
  assert.match(host.innerHTML,/BLUE #/);
  assert.match(host.innerHTML,/ОЧКИ RED/);
  assert.match(host.innerHTML,/GREEN \+ BLUE \+ RED/);
  assert.equal((host.innerHTML.match(/class="rs-hero"/g)||[]).length,1);
  assert.doesNotMatch(host.innerHTML,/rs-list-row/);
  render(host,frame(set,count));
  assert.match(host.innerHTML,/ЛИДЕР ПОСЛЕ ТРЁХ ЭТАПОВ/);
  assert.match(host.innerHTML,/aria-label="Зевс с молнией"/);
  assert.doesNotMatch(host.innerHTML,/rs-list-row/);
  render(host,frame(set,count+1));
  assert.match(host.innerHTML,/class="rs-list"/);
  const positions=[...host.innerHTML.matchAll(/<span class="rs-list-place">(\d+)<\/span>/g)].map(x=>Number(x[1]));
  assert.deepEqual(positions,Array.from({length:count},(_,i)=>i+1));
  assert.equal((host.innerHTML.match(/class="rs-list-row/g)||[]).length,count);
  assert.match(host.innerHTML,/ВПЕРЕДИ — SECRET JACK И ГОЛОСОВАНИЕ/);
  assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
}
const page=fs.readFileSync('sochi_show/static/red-preview.html','utf8');
const screen=fs.readFileSync('sochi_show/static/screen.js','utf8');
const screenHTML=fs.readFileSync('sochi_show/static/screen.html','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.html','utf8');
const adminJS=fs.readFileSync('sochi_show/static/admin.js','utf8');
assert.match(page,/ДЕМО RED · НЕ ЭФИР/);
assert.match(page,/red-preview.js/);
assert.match(screenHTML,/red-show\.js/);
assert.match(screen,/scene==='red_show'/);
assert.match(screen,/\['green_show','blue_show','red_show'\]/);
assert.match(admin,/id="red-director"/);
assert.match(admin,/red-show-next/);
assert.match(adminJS,/renderRedDirector\(\)/);
assert.match(adminJS,/action:'red-show-step'/);
console.log('RED visuals PASS: summit cabin static, 10/11 rankings, Jack animation, reveal and controls');
