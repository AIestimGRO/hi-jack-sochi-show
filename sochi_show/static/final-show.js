'use strict';
/* HI, JACK — HI, SOCHI / FINAL CEREMONY
   0 veil, 1 bronze, 2 silver, 3 gold, 4 official ranking, 5 champion.
   Render uses ONLY published final_view: no private votes/standings.
 */
window.FinalShow=(()=>{
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=n=>new Intl.NumberFormat('ru-RU').format(n||0);
 const iconRank=n=>window.SochiRankMascots?.render(n)||'<span>♠</span>';
 const jack=()=>`<div class="gs-jack-animation" aria-label="Анимированный Валет с мечом">
   <img class="gs-jack-animation-image" alt="Валет с мечом HI, JACK"
        src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}" loading="eager">
   <div class="gs-jack-animation-tagline">ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</div>
 </div>`;
 const route=()=>`<div class="gs-route-markers">${[
  'GREEN ✓','BLUE ✓','RED ✓','JACK ✓','ГОЛОСА ✓','ВЕРШИНА ★'
 ].map(x=>`<div class="gs-route-marker lit"><i></i><span>${x}</span></div>`).join('')}</div>`;
 const medal=n=>['','ЗОЛОТО','СЕРЕБРО','БРОНЗА'][n]||'ПРИЗЁР';
 const numeral=n=>['','I','II','III'][n]||String(n);
 const trophy=`<svg class="fs-trophy-svg" viewBox="0 0 180 200" xmlns="http://www.w3.org/2000/svg" aria-label="Золотой кубок" role="img">
  <defs><linearGradient id="fs-cup" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff4c7"/><stop offset=".45" stop-color="#e8af65"/><stop offset="1" stop-color="#9c563c"/></linearGradient></defs>
  <path d="M43 23h94l-10 87c-3 22-20 36-37 36s-34-14-37-36L43 23Z" fill="url(#fs-cup)" stroke="#ffe6a4" stroke-width="5"/>
  <path d="M43 39H16v19c0 38 21 59 49 60M137 39h27v19c0 38-21 59-49 60" stroke="#f8dca1" stroke-width="9" fill="none" stroke-linejoin="round"/>
  <path d="M90 144v28M61 174h58v13H61Z" fill="#e2ad70" stroke="#ffe1a4" stroke-width="6"/>
  <path d="m90 49 10 20 22 3-16 16 4 23-20-11-20 11 4-23-16-16 22-3Z" fill="#fff5ca"/>
 </svg>`;
 function demo(count=11,tie=false){
   const vote=window.VoteShow.demo(count,'target');
   const finished=window.VoteShow.frame(vote,count+1);
   const ranking=finished.ranking.map(row=>({...row}));
   let tieResolved=false;
   if(tie&&ranking.length>1){
     ranking[1].total=ranking[0].total;
     ranking[1].place=1;
     ranking[1].tied=true;ranking[0].tied=true;
     tieResolved=true;
   }
   const champion=ranking[0];
   const podium=ranking.slice(0,3).map((r,i)=>({...r,ceremony_place:i+1,official_place:r.place}));
   return {count,ranking,podium,winner_team_id:champion.team_id,first_place_tie:tieResolved,
      demo_roster:['Демо-игрок 1','Демо-игрок 2','Демо-игрок 3']};
 }
 function frame(data,step){
   const n=Math.min(5,Math.max(0,Number(step)||0));
   const p=data.podium;
   const revealed=(n>=1?[p[2]]:[]).concat(n>=2?[p[1]]:[],n>=3?[p[0]]:[]);
   return {step:n,max_step:5,count:data.count,
     revealed,current:n>=1&&n<=3?[p[2],p[1],p[0]][n-1]:null,
     board:n>=4?data.ranking:[],
     champion:n>=5?p[0]:null,
     tie_resolved:n>=3&&data.first_place_tie,
     roster:n>=5?data.demo_roster:[]};
 }
 const isConverted=p=>p?.base_points!=null&&p.base_points!==p.chip_net;
 function scoreRibbon(p){
  const converted=isConverted(p);
  return `<div class="fs-score-breakdown">
    <div><small>${converted?'ЧИСТЫЕ ФИШКИ':'GREEN'}</small><strong>${fmt(converted?p.chip_net:p.green)}</strong></div>
    <div><small>${converted?'ОЧКИ BLUE':'BLUE'}</small><strong>${fmt(converted?p.base_points:p.blue)}</strong></div>
    <div><small>RED</small><strong>${fmt(p.red)}</strong></div>
    <div><small>SECRET JACK</small><strong>${fmt(p.secret)}</strong></div>
    <div><small>ГОЛОСА</small><strong>${fmt(p.votes)}</strong></div>
  </div>`;
 }
 function boardRow(r){
   return `<div class="fs-board-row ${r.place<=3?'fs-board-podium-'+r.place:''}">
      <span class="fs-board-rank">${r.place}</span>
      <span class="fs-board-name">${esc(r.name)}${r.tied?'<small> • РАВЕНСТВО ОЧКОВ</small>':''}</span>
      <span class="fs-board-green">${fmt(isConverted(r)?r.chip_net:r.green)}</span>
      <span class="fs-board-blue">${fmt(isConverted(r)?r.base_points:r.blue)}</span>
      <span class="fs-board-red">${fmt(r.red)}</span>
      <span class="fs-board-bonus">${fmt((r.secret||0)+(r.votes||0))}</span>
      <span class="fs-board-total">${fmt(r.total)}</span>
   </div>`;
 }
 function podiumTile(p){
   return `<div class="fs-podium-tile fs-podium-${p.ceremony_place}">
      <span class="fs-podium-icon">${iconRank(p.ceremony_place)}</span>
      <span class="fs-podium-metal">${medal(p.ceremony_place)}</span>
      <strong>${esc(p.name)}</strong>
      <span class="fs-podium-points">${fmt(p.total)} ОЧКОВ</span>
      ${p.official_place!==p.ceremony_place?'<small>Место по очкам: #'+p.official_place+'</small>':''}
   </div>`;
 }
 function render(host,data){
  const step=Math.min(5,Math.max(0,Number(data?.step)||0));
  const intro=step===0,board=step===4,champion=step===5;
  const p=data?.current,win=data?.champion;
  const converted=(data?.board||[]).some(isConverted)||isConverted(p)||isConverted(win);
  const titles=[
    'ВРЕМЯ<br><em>ПОБЕДИТЕЛЕЙ</em>',
    'ТРЕТЬЯ<br><em>ВЕРШИНА</em>',
    'ВТОРАЯ<br><em>ВЕРШИНА</em>',
    'ЗОЛОТАЯ<br><em>ВЕРШИНА</em>',
    'ФИНАЛЬНЫЙ<br><em>РЕЙТИНГ</em>',
    'ВЕРШИНА<br><em>ПОКОРЕНА</em>'
  ];
  const mode=intro?'intro':board?'board':champion?'champion':'reveal';
  const currentCeremony=p?.ceremony_place||0;
  const winningTeam=win?.name||'';
  host.className='scene green-show-stage final-show-stage';
  host.innerHTML=`<div class="green-experience final-experience fs-${mode}" data-step="${step}">
    ${window.GreenShow.alpineArt('red')}
    <div class="gs-atmosphere"></div>
    <header class="gs-header"><div class="gs-brand">
      <img src="/sochi/static/hi-jack-logo.svg" alt="">
      <div><small>HI, JACK CLUB · 07.11.2026</small><strong>HI, JACK <em>— HI, SOCHI</em></strong></div>
    </div><div class="gs-step-label"><span class="gs-live-dot"></span> FINAL / SUMMIT</div></header>
    <div class="gs-content">
      <div class="gs-main">
        <div class="gs-kicker">ПОСЛЕ GREEN · BLUE · RED · SECRET JACK · ГОЛОСОВ</div>
        <h1 class="gs-title">${titles[step]}</h1>
        <div class="gs-section-rule"></div>
        ${intro?
          `<div class="fs-intro-lead">Все этапы пройдены. <b>Все бонусы учтены.</b><br>
          Осталось назвать тех, кто добрался до вершины.</div>
          <div class="fs-sealed-podium" aria-label="Три призовых места">
            <div><strong>III</strong><small>СКРЫТО</small></div>
            <div><strong>II</strong><small>СКРЫТО</small></div>
            <div><strong>I</strong><small>СКРЫТО</small></div>
          </div>
          <div class="fs-intro-caption">ВПЕРЕДИ — ТРИ ГЛАВНЫХ ОБЪЯВЛЕНИЯ</div>`:
          board?
            `<div class="fs-board-label">ВСЕ ТУРНИРЫ + SECRET JACK + ГОЛОСА КАПИТАНОВ</div>
              <div class="fs-board-head"><span>№</span><span>КОМАНДА</span><span>${converted?'ФИШКИ':'GREEN'}</span><span>${converted?'ОЧКИ':'BLUE'}</span><span>RED</span><span>БОНУС</span><span>ИТОГО</span></div>
              <div class="fs-board-list" style="--rank-count:${data.count}">${(data.board||[]).map(boardRow).join('')}</div>
              <div class="fs-board-footer">РЕЙТИНГ ЗАФИКСИРОВАН · ВПЕРЕДИ — ЧЕМПИОНСКАЯ ЦЕРЕМОНИЯ</div>`:
          champion?
            `<div class="fs-confetti" aria-hidden="true">${Array.from({length:26},(_,i)=>`<i style="--n:${i};--delay:${i%7}"></i>`).join('')}</div>
              <div class="fs-champion-main">
                <div class="fs-champion-cup">${trophy}</div>
                <div class="fs-champion-detail">
                  <div class="fs-champion-kicker">ПОБЕДИТЕЛЬ HI, JACK — HI, SOCHI</div>
                  <div class="fs-champion-name">${esc(winningTeam)}</div>
                  <div class="fs-champion-total">${fmt(win?.total)} <small>ОЧКОВ</small></div>
                  ${data.tie_resolved?'<div class="fs-tie-note">НИЧЬЯ ПО ОЧКАМ · РЕШЕНИЕ ОРГАНИЗАТОРА</div>':''}
                </div>
              </div>
              <div class="fs-champion-roster"><small>КОМАНДА ПОБЕДИТЕЛЕЙ</small>
                <div>${(data.roster||[]).map(name=>`<span>${esc(name)}</span>`).join('')||'<span>HI, JACK CLUB</span>'}</div>
              </div>
              <div class="fs-victory-tagline">SOCHI IS CALLING. HI, JACK IS ANSWERING.</div>`:
            `<div class="fs-medal-label">ПРИЗОВОЕ МЕСТО · ${medal(currentCeremony)} · ${numeral(currentCeremony)}</div>
              <div class="fs-hero-reveal">
                <div class="fs-hero-symbol">${iconRank(currentCeremony)}</div>
                <div class="fs-hero-number">${currentCeremony}<small>МЕСТО</small></div>
                <div class="fs-hero-info">
                  <div class="fs-hero-name">${esc(p?.name||'')}</div>
                  <div class="fs-hero-total">${fmt(p?.total)} <small>ОЧКОВ</small></div>
                  ${p?.official_place!==currentCeremony?'<div class="fs-tie-note">МЕСТО ПО ОЧКАМ #'+p.official_place+' · НИЧЬЯ</div>':''}
                </div>
              </div>
              ${scoreRibbon(p||{})}
              <div class="fs-reveal-caption">ОБЪЯВЛЕНО ПРИЗЁРОВ: ${step} / 3</div>`}
      </div>
      <aside class="gs-side">
        ${jack()}
        <div class="gs-route">${route()}</div>
        <div class="gs-side-bottom"><b>★</b><span>HI, SOCHI<br>SUMMIT</span><i>♠</i></div>
      </aside>
    </div>
    <footer class="gs-footer"><span>FINAL SHOW / ${intro?'ОЖИДАНИЕ':board?'ПОЛНЫЙ РЕЙТИНГ':champion?'ПОБЕДА':'ПОДИУМ'}</span>
      <span>${champion?'HI, JACK — HI, SOCHI':board?'ПОСЛЕДНИЙ КАДР ВПЕРЕДИ':'ПУТЬ К ВЕРШИНЕ'}</span>
      <span>${step} / 5</span>
    </footer>
  </div>`;
 }
 return {render,demo,frame};
})();
