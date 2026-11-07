/* Browser-free vote show tests: prefix disclosure, both bonus modes and fixed Jack. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const ctx={window:{},Intl};
for(const name of ['rank-mascots','jack-sword-motion','green-show','blue-show','red-show','vote-show']){
  vm.runInNewContext(fs.readFileSync('sochi_show/static/'+name+'.js','utf8'),ctx);
}
const {demo,frame,render}=ctx.window.VoteShow;
const cabin=s=>{
  const m=s.match(/class="alpine-cabin" transform="translate\((\d+\.\d+) (\d+\.\d+)\)"/);
  assert.ok(m);return m[0];
};
const host={className:'',innerHTML:''};
for(const count of [10,11]){
 for(const mode of ['target','voter']){
  const data=demo(count,mode);
  const baseSum=data.base_ranking.reduce((acc,r)=>acc+r.total,0);
  render(host,frame(data,0));
  const initialCabin=cabin(host.innerHTML);
  assert.match(host.innerHTML,/CAPTAINS \/ VOTE/);
  assert.match(host.innerHTML,/ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ/);
  assert.match(host.innerHTML,/data:image\/gif;base64,/);
  assert.doesNotMatch(host.innerHTML,/vs-vote-card/,'intro must be spoiler-free');
  assert.doesNotMatch(host.innerHTML,/vs-rank-row/);
  const initialScore=frame(data,0);
  assert.equal(initialScore.revealed.length,0);
  assert.equal(initialScore.ranking.reduce((acc,r)=>acc+r.votes,0),0);
  assert.equal(initialScore.mode,mode);
  for(const step of [1,2,Math.ceil(count/2),count,count+1]){
    const view=frame(data,step);
    render(host,view);
    assert.equal(cabin(host.innerHTML),initialCabin,'captain vote must not move the cabin');
    assert.match(host.innerHTML,/gs-jack-animation-image/);
    assert.equal(view.revealed.length,Math.min(step,count));
    assert.equal(view.ranking.reduce((acc,r)=>acc+r.total,0),
      baseSum+10000*Math.min(step,count),'each revealed vote is +10,000 once');
    if(step<=count){
      assert.match(host.innerHTML,/vs-vote-card/);
      assert.match(host.innerHTML,/vs-target/);
      assert.match(host.innerHTML.replace(/\u00a0/g,' '),/\+10 000/);
      assert.match(host.innerHTML,/ПРОМЕЖУТОЧНОЕ МЕСТО/);
      assert.doesNotMatch(host.innerHTML,/vs-rank-row/,'final table not yet shown');
      assert.ok(!host.innerHTML.includes(data.all_demo_votes[step]?.captain_name||'UNLIKELY'),
        'future captain is not disclosed on step '+step);
    }else{
      assert.match(host.innerHTML,/vs-rank-list/);
      assert.equal((host.innerHTML.match(/class="vs-rank-row/g)||[]).length,count);
      assert.match(host.innerHTML,/ЦЕРЕМОНИЯ ПОБЕДИТЕЛЕЙ/);
      assert.match(host.innerHTML,/ГОЛОСА<br><em>УЧТЕНЫ<\/em>/);
    }
  }
  const end=frame(data,count+1);
  assert.equal(end.summary,true);
  const totalVotePoints=end.ranking.reduce((acc,r)=>acc+r.votes,0);
  assert.equal(totalVotePoints,count*10000);
  if(mode==='voter')assert.ok(end.ranking.every(r=>r.votes===10000),
    'each team receives one vote in voter mode');
  const first=frame(data,1);
  assert.equal(first.current.receiver_team_id,
    mode==='target'?first.current.target_team_id:first.current.voter_team_id);
 }
}

// Live final-table vote chips are 20k, while historical demos stay 10k.
const live=frame(demo(10,'target'),1);
live.final_table=true;
live.vote_chips=20000;
live.current={...live.current,points:20000};
render(host,live);
assert.match(host.innerHTML.replace(/\u00a0/g,' '),/\+20 000/);
assert.match(host.innerHTML,/ФИШЕК/);

const screen=fs.readFileSync('sochi_show/static/screen.js','utf8');
const html=fs.readFileSync('sochi_show/static/screen.html','utf8');
const admin=fs.readFileSync('sochi_show/static/admin.html','utf8');
const adminJS=fs.readFileSync('sochi_show/static/admin.js','utf8');
const preview=fs.readFileSync('sochi_show/static/vote-preview.html','utf8');
assert.match(screen,/scene==='vote_show'/);
assert.match(screen,/\['green_show','blue_show','red_show','secret_show','vote_show','final_show','captains'\]/);
assert.match(html,/vote-show\.css/);
assert.match(html,/vote-show\.js/);
assert.match(admin,/id="vote-show-start"/);
assert.match(admin,/id="vote-show-next"/);
assert.match(admin,/href="\/sochi\/preview\/vote"/);
assert.match(adminJS,/renderVoteDirector\(\)/);
assert.match(adminJS,/show_mode:'cinematic'/);
assert.match(preview,/ДЕМО ГОЛОСОВ КАПИТАНОВ · НЕ ЭФИР/);
console.log('CAPTAIN VOTE visuals PASS: 10/11 teams, both bonus modes, no future votes, Jack throughout');
