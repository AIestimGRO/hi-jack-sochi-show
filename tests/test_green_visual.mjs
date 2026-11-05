/* Visual smoke tests for static GREEN station and unique rank-character SVGs. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context={window:{},Intl};
vm.runInNewContext(fs.readFileSync('sochi_show/static/rank-mascots.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('sochi_show/static/jack-sword-motion.js','utf8'),context);
const gifB64=context.window.JackSwordGifB64;
assert.equal(gifB64.length,19412,'complete transparent GIF must be committed');
let gifHash=2166136261;
for(const ch of gifB64)gifHash=Math.imul(gifHash^ch.charCodeAt(0),16777619)>>>0;
assert.equal(gifHash,0x2a6cdead,'GIF must match verified original-with-background-removed');
const gifBytes=Buffer.from(gifB64,'base64');
assert.equal(gifBytes.subarray(0,6).toString('ascii'),'GIF89a');
assert.equal(gifBytes.readUInt16LE(6),200);
assert.equal(gifBytes.readUInt16LE(8),200);
assert.equal(gifBytes[gifBytes.length-1],0x3b,'GIF ends correctly');

vm.runInNewContext(fs.readFileSync('sochi_show/static/green-show.js','utf8'),context);
const {demo,frame,render}=context.window.GreenShow;
const mascots=context.window.SochiRankMascots;
const host={className:'',innerHTML:''};
const cabinPosition=html=>{
  const m=html.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(m,'one visible cable car has a reproducible location');
  return m[0];
};

for(const count of [10,11]){
  const data=demo(count);
  render(host,frame(data,0));
  const station=cabinPosition(host.innerHTML);
  assert.match(host.innerHTML,/class="gs-jack-animation-image"/,'transparent animated mascot appears in right-side place');
  assert.match(host.innerHTML,/src="data:image\/gif;base64,R0lGODlh/,'inline GIF is used with no external dependency');
  assert.doesNotMatch(host.innerHTML,/gs-mountain-badge/,'old circular HI SOCHI badge is gone');
  assert.match(host.innerHTML,/gs-jack-animation-tagline/,'poker slogan remains beneath the mascot');

  assert.equal((host.innerHTML.match(/class="alpine-cabin"/g)||[]).length,1,'single cabin');
  assert.match(host.innerHTML,/GREEN ✓/,'GREEN checkpoint is marked completed');
  assert.match(host.innerHTML,/d="M730 790 C930 652 1170 427 1440 245"/,'one real cable');
  assert.equal((host.innerHTML.match(/id="sochi-cable"/g)||[]).length,1);
  assert.doesNotMatch(host.innerHTML,/fill="#7e8d54"/,'no second green cabin');
  assert.doesNotMatch(host.innerHTML,/M1140 285L1780 440/,'no disconnected cable');
  assert.notEqual(station,'class="alpine-cabin" transform="translate(730.0 790.0)"',
    'cabin has finished the first phase and parks at GREEN, not START');

  // Revealing the last, middle and first places never moves the cabin.
  for(const step of [1,Math.floor(count/2),count,count+1]){
    render(host,frame(data,step));
    assert.equal(cabinPosition(host.innerHTML),station,'rank changes must not change cabin location');
  }

  // A new badge belongs to the place, not the team number or next step.
  render(host,frame(data,1));
  assert.match(host.innerHTML,new RegExp('aria-label="'+(count===11?'Улитка на старте':'Хромая бабушка с тростью')+'"'));
  render(host,frame(data,count===11?3:2));
  assert.match(host.innerHTML,/aria-label="Бабушка без трости"/);
  render(host,frame(data,count));
  assert.match(host.innerHTML,/aria-label="Зевс с молнией"/);
  assert.match(host.innerHTML,/gs-hero-mascot/);

  // Final GREEN is a 1..N classic list, with a unique badge in every row.
  // After the Zeus 1st-place reveal (N), immediately show the board (N+1).
  render(host,frame(data,count));
  assert.match(host.innerHTML,/class="gs-hero-mascot"/,'first place is a hero reveal');
  assert.doesNotMatch(host.innerHTML,/class="gs-ranking-list"/,'first place is not yet the overall board');
  render(host,frame(data,count+1));
  assert.match(host.innerHTML,/class="gs-ranking-list"/,'next press goes directly to results');
  assert.equal(data.max_step,count+1);
  assert.equal((host.innerHTML.match(/class="gs-ranking-row/g)||[]).length,count);
  assert.equal((host.innerHTML.match(/class="gs-ranking-mascot"/g)||[]).length,count);
  assert.match(host.innerHTML,/class="gs-ranking-list"/);
  assert.doesNotMatch(host.innerHTML,/gs-overview-cards|gs-team-tile/);
  const places=[...host.innerHTML.matchAll(/<div class="gs-ranking-place"><b>(\d+)<\/b>/g)].map(m=>Number(m[1]));
  assert.deepEqual(places,[...Array(count)].map((_,i)=>i+1));
  assert.match(host.innerHTML,/gs-ranking-row gs-rank-1/);
  assert.match(host.innerHTML,/Паса не имеем/);
  assert.match(host.innerHTML,/aria-label="Зевс с молнией"/);
  assert.match(host.innerHTML,/aria-label="Хромая бабушка с тростью"/);
  assert.match(host.innerHTML,/aria-label="Бабушка без трости"/);
  assert.match(host.innerHTML,/БЛЕФ · СТЕК · ОЛЛ-ИН/,'poker-specific badge slogan');
  assert.doesNotMatch(host.innerHTML,/ВЫСОТА · ВОЛЯ · ПОБЕДА/);
}

assert.equal(Object.keys(mascots).sort().join(','),'label,render');
for(const rank of Array.from({length:11},(_,i)=>i+1)){
  const svg=mascots.render(rank);
  assert.match(svg,/viewBox="0 0 100 100"/);
  assert.match(svg,new RegExp('gs-rank-symbol-'+rank));
  assert.match(svg,new RegExp('aria-label="'+mascots.label(rank)+'"'));
}
console.log('GREEN visuals PASS: stationary cabin at GREEN + distinct rank mascots + ordered results (10/11 teams)');
