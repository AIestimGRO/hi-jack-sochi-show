/* Browser-free smoke tests for the SVG route and 10/11 team GREEN scoreboard. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync('sochi_show/static/green-show.js','utf8');
const context={window:{},Intl};
vm.runInNewContext(source,context);
const {demo,frame,render}=context.window.GreenShow;
const host={className:'',innerHTML:''};

for(const count of [10,11]){
  const data=demo(count);
  render(host,frame(data,0));
  assert.match(host.innerHTML, /class="alpine-cabin"/, 'a cabin must be visible at the start');
  assert.equal((host.innerHTML.match(/class="alpine-cabin"/g)||[]).length,1, 'only one cable car');
  assert.match(host.innerHTML, /transform="translate\(730\.0 790\.0\)"/, 'cabin is attached at START');
  assert.match(host.innerHTML, /d="M730 790 C930 652 1170 427 1440 245"/, 'cable starts where cabin is');
  assert.equal((host.innerHTML.match(/id="sochi-cable"/g)||[]).length,1, 'one named cable');
  assert.doesNotMatch(host.innerHTML, /fill="#7e8d54"/, 'remove the second green car');
  assert.doesNotMatch(host.innerHTML, /M1140 285L1780 440/, 'remove disconnected cable');
  render(host,frame(data,Math.floor(count/2)));
  assert.equal((host.innerHTML.match(/class="alpine-cabin"/g)||[]).length,1,'one car throughout reveal');
  render(host,frame(data,count+2));
  assert.equal((host.innerHTML.match(/class="gs-ranking-row/g)||[]).length,count, 'all teams shown as rows');
  assert.match(host.innerHTML, /class="gs-ranking-list"/,'classic vertical list');
  assert.doesNotMatch(host.innerHTML,/gs-overview-cards|gs-team-tile/,'no grid tiles');
  const places=[...host.innerHTML.matchAll(/<div class="gs-ranking-place"><b>(\d+)<\/b>/g)].map(m=>Number(m[1]));
  assert.equal(places.length,count);
  assert.deepEqual(places,[...Array(count)].map((_,i)=>i+1),'ranking must descend 1 through N');
  const firstRow=host.innerHTML.match(/<div class="gs-ranking-row gs-rank-1">([\s\S]*?)<\/div>\s*<div class="gs-ranking-row/);
  assert.ok(firstRow,'1st place should have podium highlighting');
  assert.match(firstRow[1],/Паса не имеем/,'1st team must be the demo leader');
}
console.log('GREEN visuals PASS: single cabin, real cable, START, ranking 1→N (10/11 teams)');
