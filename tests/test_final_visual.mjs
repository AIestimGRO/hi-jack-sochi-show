/* Six-step final ceremony: privacy, podium order, fixed summit cabin and animated Jack. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const ctx={window:{},Intl};
for(const name of ['rank-mascots','jack-sword-motion','green-show','blue-show','red-show','vote-show','final-show']){
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+name+'.js','utf8'),ctx);
}
const {demo,frame,render}=ctx.window.FinalShow;
const cabin=html=>{
  const m=html.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(m,'there must be precisely one cable car');
  return m[0];
};
const host={className:'',innerHTML:''};
for(const count of [10,11]){
 for(const tied of [false,true]){
  const data=demo(count,tied);
  const snapshot=data.ranking.map(r=>({team_id:r.team_id,total:r.total}));
  const total=()=>data.ranking.reduce((x,r)=>x+r.total,0);
  const initialTotal=total();
  assert.equal(data.ranking.length,count);
  assert.equal(data.podium.length,3);
  render(host,frame(data,0));
  const fixedCabin=cabin(host.innerHTML);
  assert.match(host.innerHTML,/FINAL \/ SUMMIT/);
  assert.match(host.innerHTML,/STAGE|ВРЕМЯ<br><em>ПОБЕДИТЕЛЕЙ/);
  assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
  assert.match(host.innerHTML,/data:image\/gif;base64,/);
  assert.doesNotMatch(host.innerHTML,/fs-hero-name/,'intro must not name winner');
  assert.doesNotMatch(host.innerHTML,/fs-board-row/,'intro has no score table');
  assert.doesNotMatch(host.innerHTML,/fs-champion-name/);
  assert.equal(frame(data,0).board.length,0);
  assert.equal(frame(data,0).revealed.length,0);
  const seen=[];
  for(let step=1;step<=5;step++){
    const view=frame(data,step);
    render(host,view);
    assert.equal(cabin(host.innerHTML),fixedCabin,'cable car stays on RED summit');
    assert.match(host.innerHTML,/gs-jack-animation-image/);
    assert.equal(view.revealed.length,Math.min(step,3));
    assert.equal(total(),initialTotal,'page transitions never change points');
    if(step<=3){
      assert.match(host.innerHTML,/fs-hero-name/);
      assert.match(host.innerHTML,/fs-hero-total/);
      assert.match(host.innerHTML,/fs-score-breakdown/);
      assert.doesNotMatch(host.innerHTML,/fs-board-row/,'podium before official leaderboard');
      assert.equal(view.current.ceremony_place,4-step);
      assert.equal(view.board.length,0);
      assert.equal(view.champion,null);
      seen.push(view.current.team_id);
      assert.equal(seen.length,new Set(seen).size);
    }else if(step===4){
      assert.match(host.innerHTML,/fs-board-list/);
      assert.equal((host.innerHTML.match(/class="fs-board-row/g)||[]).length,count);
      assert.equal(view.board.length,count);
      assert.equal(view.champion,null);
      assert.doesNotMatch(host.innerHTML,/fs-champion-name/);
    }else{
      assert.match(host.innerHTML,/fs-champion-name/);
      assert.match(host.innerHTML,/class="fs-confetti"/);
      assert.match(host.innerHTML,/fs-trophy-svg/);
      assert.match(host.innerHTML,/SOCHI IS CALLING/);
      assert.equal(view.champion.team_id,data.winner_team_id);
      assert.equal(view.roster.length,3);
      assert.ok(host.innerHTML.includes(view.champion.name));
    }
    assert.equal(view.tie_resolved,tied&&step>=3);
  }
  assert.deepEqual(seen,[data.podium[2].team_id,data.podium[1].team_id,data.podium[0].team_id]);
  assert.deepEqual(snapshot.map(r=>r.total),data.ranking.map(r=>r.total));
  if(tied){
    assert.equal(data.podium[0].official_place,1);
    assert.equal(data.podium[1].official_place,1);
    assert.match(host.innerHTML,/НИЧЬЯ ПО ОЧКАМ/);
  }
 }
}
const html=fs.readFileSync('sochi_show/static/screen.html','utf8');
const screen=fs.readFileSync('sochi_show/static/screen.js','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.html','utf8');
const adminJS=fs.readFileSync('sochi_show/static/admin.js','utf8');
const preview=fs.readFileSync('sochi_show/static/final-preview.html','utf8');
const css=fs.readFileSync('sochi_show/static/final-show.css','utf8');
assert.match(html,/final-show.js\?v=final-v1/);
assert.match(html,/final-show.css\?v=final-v1/);
assert.match(screen,/scene==='final_show'/);
assert.match(screen,/\['green_show','blue_show','red_show','secret_show','vote_show','final_show'\]/);
assert.match(admin,/id="final-director"/);
assert.match(admin,/id="final-show-start"/);
assert.match(admin,/id="final-show-next"/);
assert.match(adminJS,/renderFinalDirector\(\)/);
assert.match(adminJS,/action:'final-show-step'/);
assert.match(preview,/ДЕМО ФИНАЛА · НЕ ЭФИР/);
assert.match(css,/fs-confetti/);
console.log('FINAL visuals PASS: 10/11 teams, tie, podium #3/#2/#1, final score board, champion and animated Jack');
