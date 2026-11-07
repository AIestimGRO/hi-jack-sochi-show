'use strict';
/* HI, JACK — HI, SOCHI: CAPTAINS' VOTE SHOW.
 * Only the already-revealed ballot prefix is ever received by the projector.
 * The source of all chip awards remains the server's frozen published votes.
 */
window.VoteShow=(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=n=>new Intl.NumberFormat('ru-RU').format(n||0);
  const rankIcon=n=>window.SochiRankMascots?.render(n)||'<span>♠</span>';
  const jack=()=>`<div class="gs-jack-animation" aria-label="Валет HI, JACK с мечом">
     <img class="gs-jack-animation-image" alt="Валет с мечом — анимация клуба"
       src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}" loading="eager">
     <div class="gs-jack-animation-tagline">ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</div>
  </div>`;
  const route=(table=false)=>'<div class="gs-route-markers">'+[
    ['GREEN ✓',true],['BLUE ✓',true],[table?'СТЕКИ ✓':'RED ✓',true],['ГОЛОСА',true]
  ].map(([s,lit])=>`<div class="gs-route-marker ${lit?'lit':''}"><i></i><span>${s}</span></div>`).join('')+'</div>';

  // Used exclusively for an independent anonymous rehearsal.
  function demo(count=11,mode='target'){
    const previous=window.RedShow.demo(count).demo_ranking;
    const base=previous.map(r=>({...r,secret:0,votes:0,total:r.total}));
    const ids=count===11?[2,8,6,5,11,3,9,7,1,10,4]:[2,8,6,5,3,9,7,1,10,4];
    for(const recipient of [3,5]){
      const team=base.find(r=>r.team_id===recipient);
      team.secret+=10000;team.total+=10000;
    }
    base.sort((a,b)=>b.total-a.total||a.team_id-b.team_id);
    base.forEach((r,i)=>r.place=i>0&&r.total===base[i-1].total?base[i-1].place:i+1);
    const byId=new Map(base.map(r=>[r.team_id,r]));
    const votes=ids.map((id,i)=>{
      const voter=i+1;
      const target=id===voter?(voter%count)+1:id;
      const receiver=mode==='target'?target:voter;
      return {voter_team_id:voter,target_team_id:target,receiver_team_id:receiver,
        voter_name:byId.get(voter).name,target_name:byId.get(target).name,
        receiver_name:byId.get(receiver).name,
        captain_name:'Демо-капитан №'+voter,captain_player_id:null,points:10000};
    });
    return {all_demo_votes:votes,base_ranking:base,mode};
  }
  function compute(base,visible){
    const ranks=base.map(r=>({...r}));
    const original=new Map(ranks.map(r=>[r.team_id,r.place]));
    for(const vote of visible){
      const team=ranks.find(r=>r.team_id===vote.receiver_team_id);
      if(team){team.votes=(team.votes||0)+vote.points;team.total+=vote.points}
    }
    ranks.sort((a,b)=>b.total-a.total||a.team_id-b.team_id);
    ranks.forEach((r,i)=>{
      r.place=i>0&&r.total===ranks[i-1].total?ranks[i-1].place:i+1;
      r.before_place=original.get(r.team_id);r.move=r.before_place-r.place;
    });
    return ranks;
  }
  function frame(data,step){
    const count=data.all_demo_votes.length;
    const n=Math.max(0,Math.min(count+1,Number(step)||0));
    const visible=data.all_demo_votes.slice(0,Math.min(n,count));
    const ranking=compute(data.base_ranking,visible);
    const current=n>0&&n<=count?{...visible[visible.length-1]}:null;
    if(current){
      const team=ranking.find(r=>r.team_id===current.receiver_team_id);
      current.place=team.place;current.before_place=team.before_place;
      current.total=team.total;current.vote_points=team.votes;
    }
    return {step:n,count,max_step:count+1,mode:data.mode,summary:n===count+1,
      revealed:visible,current,ranking};
  }
  const rankedRow=row=>`<div class="vs-rank-row ${row.place<=3?'vs-podium-'+row.place:''}">
    <span class="vs-rank-icon">${rankIcon(row.place)}</span>
    <span class="vs-rank-place">${row.place}</span>
    <span class="vs-rank-name">${esc(row.name)}</span>
    <span class="vs-rank-bounty">${fmt(row.secret)}</span>
    <span class="vs-rank-votes">${row.votes?'+':''}${fmt(row.votes)}</span>
    <span class="vs-rank-total">${fmt(row.total)}</span>
  </div>`;
  function render(host,data){
    const count=Number(data?.count)||10;
    const step=Math.max(0,Math.min(count+1,Number(data?.step)||0));
    const intro=step===0,board=step===count+1;
    const vote=data.current||null;
    const ranking=data.ranking||[];
    const received=vote?ranking.find(r=>r.team_id===vote.receiver_team_id):null;
    const winner=board?ranking[0]:null;
    const mode=data.mode==='voter'?'ГОЛОСУЮЩЕЙ':'ВЫБРАННОЙ';
    const unit=data.final_table?'фишек':'очков';
    const unitBig=data.final_table?'ФИШЕК':'ОЧКОВ';
    const bonus=Number(data.vote_chips)||(data.final_table?20000:10000);
    const title=intro?'ПОСЛЕДНИЙ<br><em>ХОД</em>':board?'ГОЛОСА<br><em>УЧТЕНЫ</em>':'РЕШЕНИЕ<br><em>КАПИТАНА</em>';
    host.className='scene green-show-stage vote-show-stage';
    host.innerHTML=`<div class="green-experience vote-experience vs-${intro?'intro':board?'board':'reveal'}" data-step="${step}">
      ${window.GreenShow.alpineArt('red')}
      <div class="gs-atmosphere"></div>
      <header class="gs-header">
        <div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt="">
          <div><small>HI, JACK CLUB · 07.11.2026</small><strong>HI, JACK <em>— HI, SOCHI</em></strong></div>
        </div>
        <div class="gs-step-label"><span class="gs-live-dot"></span> CAPTAINS / VOTE</div>
      </header>
      <div class="gs-content">
        <div class="gs-main">
          <div class="gs-kicker">${data.final_table?'ПЕРЕД RED · ВЫДАЧА ФИШЕК ПО ГОЛОСАМ':'ПОСЛЕ SECRET JACK / ПОСЛЕДНЯЯ ИНТРИГА'}</div>
          <h1 class="gs-title">${title}</h1>
          <div class="gs-section-rule"></div>
          ${intro?
            `<div class="vs-intro-text"><strong>${count} КАПИТАНОВ.</strong> У каждого — один голос.<br>
            Каждый голос даёт <b>${fmt(bonus)} ${unit}</b> и может изменить итоговый рейтинг.</div>
            <div class="vs-intro-stamp">БОНУС ПОЛУЧАЕТ ${mode} КОМАНДА</div>
            <div class="vs-dramatic-word">ПУСТЬ РЕШАТ ГОЛОСА ♠</div>`:
            board?
              `<div class="vs-summary-label">${data.final_table?'СТЕКИ КАПИТАНОВ ПЕРЕД RED · SECRET JACK + ГОЛОСА':'ИТОГОВЫЙ РЕЙТИНГ ПОСЛЕ ВСЕХ БОНУСОВ · SECRET JACK + ГОЛОСОВАНИЕ'}</div>
                <div class="vs-rank-head"><span></span><span>№</span><span>КОМАНДА</span><span>JACK</span><span>ГОЛОСА</span><span>ИТОГО</span></div>
                <div class="vs-rank-list" style="--rank-count:${count}">${ranking.map(rankedRow).join('')}</div>
                <div class="vs-winner-teaser"><strong>ЛИДЕР: ${esc(winner?.name||'—')}</strong><span>ВПЕРЕДИ — ЦЕРЕМОНИЯ ПОБЕДИТЕЛЕЙ</span></div>`:
              `<div class="vs-vote-count">ГОЛОС ${step} / ${count}</div>
                <div class="vs-vote-card">
                  <div class="vs-voter">${vote?.captain_player_id?
                    `<img class="vs-captain-photo" src="/sochi/api/public/photo/${Number(vote.captain_player_id)}" alt="Фото капитана">`:
                    '<span class="vs-captain-symbol">♠</span>'}
                    <div><small>ГОЛОС КАПИТАНА · КОМАНДА №${vote?.voter_team_id||'—'}</small>
                      <strong>${esc(vote?.voter_name||'')}</strong>
                      <span>${esc(vote?.captain_name||'Капитан команды')}</span></div>
                  </div>
                  <div class="vs-vote-arrow">↓ <span>ОТДАЛ ГОЛОС ЗА</span> ↓</div>
                  <div class="vs-target">${esc(vote?.target_name||'')}</div>
                </div>
                <div class="vs-award">
                  <div><span>+${fmt(vote?.points||bonus)} ${unitBig} ПОЛУЧАЕТ</span><strong>${esc(vote?.receiver_name||'')}</strong></div>
                  <div class="vs-award-number">+${fmt(vote?.points||bonus)}</div>
                </div>
                <div class="vs-change-row">
                  <div>ПРОМЕЖУТОЧНОЕ МЕСТО <strong>#${received?.before_place||'—'} → #${vote?.place||'—'}</strong></div>
                  <div>СУММА КОМАНДЫ <strong>${fmt(vote?.total)}</strong></div>
                </div>
                <div class="gs-reveal-counter">РАСКРЫТО ГОЛОСОВ: ${Math.min(step,count)} / ${count}</div>`}
        </div>
        <aside class="gs-side">
          ${jack()}
          <div class="gs-route">${route(!!data.final_table)}</div>
          <div class="gs-side-bottom"><b>♠</b><span>CAPTAINS<br>VOTE</span><i>✦</i></div>
        </aside>
      </div>
      <footer class="gs-footer"><span>CAPTAINS VOTE / ${intro?'ЗАСТАВКА':board?'ИТОГИ':'ГОЛОС № '+step}</span>
        <span>${board?(data.final_table?'СЛЕДУЮЩИЙ ШАГ — RED ФИНАЛЬНЫЙ СТОЛ':'СЛЕДУЮЩИЙ ШАГ — ФИНАЛ'):'ПОЛНЫЙ ИТОГ НЕ РАСКРЫТ'}</span><span>${step} / ${count+1}</span>
      </footer>
    </div>`;
  }
  return {render,demo,frame};
})();
