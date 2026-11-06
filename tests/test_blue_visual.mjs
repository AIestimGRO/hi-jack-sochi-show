/* Node-powered BLUE smoke tests, no browser and no server dependencies. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const scope={window:{},Intl};
for (const file of ['rank-mascots','jack-sword-motion','green-show','blue-show']) {
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+file+'.js','utf8'),scope);
}
const {demo,frame,render}=scope.window.BlueShow;
const host={className:'',innerHTML:''};
const getCabin=html=>{
  const match=html.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(match,'BLUE has the same mountain cable car');
  return match[0];
};
for(const n of [10,11]){
  const all=demo(n);
  assert.equal(all.max_step,n+1);
  assert.equal(all.demo_ranking.length,n);
  const jumps=all.demo_ranking.filter(r=>r.move>0);
  const falls=all.demo_ranking.filter(r=>r.move<0);
  assert.ok(jumps.length>0,'BLUE reveals climbers');
  assert.ok(falls.length>0,'BLUE reveals demotions');
  all.demo_ranking.forEach(r=>{
    assert.equal(r.total,r.green+r.blue);
    assert.equal(r.move,r.green_place-r.place);
  });
  render(host,frame(all,0));
  const spot=getCabin(host.innerHTML);
  const greenSpot=getCabin((()=>{const h={};scope.window.GreenShow.render(h,scope.window.GreenShow.frame(scope.window.GreenShow.demo(n),0));return h.innerHTML})());
  assert.notEqual(spot,greenSpot,'BLUE moves cabin to camp 2 exactly once');
  assert.match(host.innerHTML,/BLUE ✓/);
  assert.match(host.innerHTML,/GREEN ✓/);
  assert.match(host.innerHTML,/STAGE 02 \/ BLUE/);
  assert.match(host.innerHTML,/class="gs-jack-animation-image"/);
  assert.match(host.innerHTML,/data:image\/gif;base64,/,'animated Jack preserved on BLUE');
  assert.doesNotMatch(host.innerHTML,/bs-hero-name/,'intro does not leak winner');

  for(const step of [1,Math.ceil(n/2),n,n+1]){
    render(host,frame(all,step));
    assert.equal(getCabin(host.innerHTML),spot,'BLUE cable car never moves between rankings');
    assert.match(host.innerHTML,/class="gs-jack-animation-image"/);
  }

  render(host,frame(all,1));
  assert.match(host.innerHTML,/GREEN #/);
  assert.match(host.innerHTML,/BLUE #/);
  assert.match(host.innerHTML,/ОЧКИ ЭТАПА BLUE/);
  assert.match(host.innerHTML,/СУММА GREEN \+ BLUE/);
  assert.ok(!host.innerHTML.includes(all.demo_ranking[0].name) ||
    all.demo_ranking[0].team_id===all.demo_ranking[n-1].team_id,
    'the leader is not revealed first');

  render(host,frame(all,n));
  assert.match(host.innerHTML,/bs-hero-name/,'winner gets its own individual hero scene');
  assert.doesNotMatch(host.innerHTML,/bs-ranking-list/);
  render(host,frame(all,n+1));
  assert.match(host.innerHTML,/bs-ranking-list/,'next scene is the final list');
  const ranks=[...host.innerHTML.matchAll(/<span class="bs-place">(\d+)<\/span>/g)].map(x=>Number(x[1]));
  assert.deepEqual(ranks,Array.from({length:n},(_,i)=>i+1));
  assert.equal((host.innerHTML.match(/class="bs-ranking-row/g)||[]).length,n);
  assert.equal((host.innerHTML.match(/class="bs-icon"/g)||[]).length,n);
  assert.match(host.innerHTML,/bs-move rise/);
  assert.match(host.innerHTML,/bs-move fall/);
  assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
}

const blueJS=fs.readFileSync('sochi_show/static/blue-show.js','utf8');
const blueCSS=fs.readFileSync('sochi_show/static/blue-show.css','utf8');
assert.doesNotMatch(blueJS,/ПОТЕРЯ|ПОДЪЁМ НА|без изменений/,'no redundant rank movement labels');
assert.match(blueJS,/#\$\{r\.green_place\} → #\$\{r\.place\}/,'overview shows old and new place');
assert.match(blueCSS,/\.bs-hero-place\{\s*line-height:1\.08;\s*gap:/,'BLUE place has explicit caption gap');
assert.doesNotMatch(blueJS,/bs-change-line">[\s\S]*?<strong class=/,'no extra gain/loss badge');
const html=fs.readFileSync('sochi_show/static/screen.html','utf8');
const js=fs.readFileSync('sochi_show/static/screen.js','utf8');
assert.match(html,/id="show-jack-persistent"/);
assert.match(html,/blue-show\.js/);
assert.match(js,/updatePersistentJack\(scene\)/);
assert.match(js,/\['green_show','blue_show','red_show'\]/);
assert.match(js,/scene==='blue_show'/);
const preview=fs.readFileSync('sochi_show/static/blue-preview.html','utf8');
assert.match(preview,/ДЕМО BLUE · НЕ ЭФИР/);
console.log('BLUE visuals PASS: static camp 2, 10/11 ranked changes, animated Jack everywhere');
