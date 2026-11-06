'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>new Intl.NumberFormat('ru-RU').format(v||0);
let version=-1,last=null,connected=false;
const titles={intro:'ЗАСТАВКА',teams:'КОМАНДЫ',green:'GREEN',blue:'BLUE',captains:'КАПИТАНЫ',red:'RED',secrets:'SECRET JACKS',votes:'ГОЛОСОВАНИЕ',final:'ФИНАЛЬНЫЙ РЕЙТИНГ',winner:'ПОБЕДИТЕЛЬ',pause:'ПАУЗА'};
const logo='<div class="stage-logo"><img class="brand-mark" src="/sochi/static/hi-jack-logo.svg" alt="Логотип Hi, Jack Club"><div>HI, JACK <span>— HI, SOCHI</span></div></div>';
const header=(title,phase='')=>`<div class="show-header">${logo}<div class="stage-tag ${phase}">${esc(title)}</div></div>`;
const avatar=(id,has)=>id&&has?`<img class="avatar" src="/sochi/api/public/photo/${id}" alt="">`:'<span>♠</span>';
function updatePersistentJack(scene){
  // GREEN/BLUE already contain a full-size Jack. The same mascot remains
  // visible in the corner of every other scene: intro, RED, Jack, vote, final...
  const slot=$('show-jack-persistent');
  const img=$('show-jack-persistent-img');
  if(!slot||!img)return;
  const integrated=['green_show','blue_show','red_show'].includes(scene);
  slot.hidden=integrated;
  if(!integrated&&!img.dataset.ready){
    img.src=window.JackSwordGifB64
      ?'data:image/gif;base64,'+window.JackSwordGifB64
      :'/sochi/static/hi-jack-logo.svg';
    img.dataset.ready='1';
  }
}
function render(state,animate=true){const scene=state.scene||'intro';const panel=$('scene');panel.className=`scene ${scene}${animate?' slide-in':''}`;const rows=state.ranking||[];
updatePersistentJack(scene);
if(scene==='red_show'){
  window.RedShow.render(panel,state.red_view||{count:state.team_count,step:0,revealed:[]});
  return;
}
if(scene==='blue_show'){
  window.BlueShow.render(panel,state.blue_view||{count:state.team_count,step:0,revealed:[]});
  return;
}
if(scene==='green_show'){
  window.GreenShow.render(panel,state.green_view||{count:state.team_count,step:0,revealed:[]});
  return;
}
if(scene==='intro'){panel.innerHTML=`${logo}<div class="mountains">◆ ▲ ◆</div><div class="prelude">7 НОЯБРЯ 2026 · ОДНА КОМАНДА — ДВА МЕСТА В СОЧИ</div>`;return}
if(scene==='pause'){panel.innerHTML=`${logo}<div class="feature-title">ПАУЗА</div><div class="feature-sub">СКОРО ПРОДОЛЖИМ</div>`;return}
if(scene==='teams'){panel.innerHTML=header('НАШИ КОМАНДЫ')+`<div class="team-tiles">${Object.entries(state.teams||{}).map(([id,name])=>`<div class="team-tile"><small>КОМАНДА №${id}</small><strong>${esc(name)}</strong></div>`).join('')}</div>`;return}
if(scene==='captains'){panel.innerHTML=header('КАПИТАНЫ')+`<div class="captain-cards">${(state.captains||[]).map(c=>`<div class="captain-card">${avatar(c.player_id,c.has_photo)}<small>КОМАНДА №${c.team_id}</small><strong>${esc(c.name)}</strong><small>${esc(state.teams[c.team_id])}</small></div>`).join('')}</div>`;return}
if(scene==='secrets'){const revealed=new Map((state.revealed_secrets||[]).map(x=>[x.slot,x]));panel.innerHTML=header('SECRET JACKS')+`<div class="feature-scene"><div class="feature-title">РАСКРЫТИЕ SECRET JACKS</div><div class="secret-cards">${[1,2,3].map(slot=>{let s=revealed.get(slot);return s?`<div class="secret-card">${avatar(s.player_id,s.has_photo)}<div class="jack-name">${esc(s.name)}</div><small>${esc(state.teams[s.jack_team_id])}</small><strong>${s.confirmed?'Выбил '+esc(s.knockout_name)+' · +10 000 → '+esc(state.teams[s.knockout_team_id]):'ОСТАЛСЯ НЕПОБЕЖДЁННЫМ'}</strong></div>`:`<div class="secret-card"><div class="unknown">♠</div><div class="jack-name">SECRET JACK №${slot}</div><small>ЛИЧНОСТЬ СКРЫТА</small></div>`}).join('')}</div></div>`;return}
if(scene==='votes'){panel.innerHTML=header('ТАЙНОЕ ГОЛОСОВАНИЕ')+`<div class="feature-scene"><div class="feature-title">ГОЛОСА КАПИТАНОВ</div><div class="voting-detail">${state.votes_published?(state.published_votes||[]).map(v=>`№${v.voter_team_id} → ${esc(state.teams[v.target_team_id])}`).join(' &nbsp; · &nbsp; '):'ОЖИДАНИЕ РАСКРЫТИЯ'}</div><div class="feature-sub">+10 000 ЗА КАЖДЫЙ ГОЛОС</div></div>`;return}
if(scene==='winner'){const max=rows[0]?.total;const tied=rows.filter(x=>x.total===max);const chosen=tied.length===1?tied[0]:tied.find(x=>x.team_id===state.winner_decision);panel.innerHTML=header('ПОБЕДИТЕЛЬ')+`<div class="feature-scene"><div class="winner-headline">ОДНА КОМАНДА — ДВА МЕСТА В СОЧИ</div><div class="winner-team">${chosen?esc(chosen.name):'НИЧЬЯ'}</div><div class="winner-score">${chosen?fmt(chosen.total)+' ОЧКОВ':'РЕШЕНИЕ ОРГАНИЗАТОРА'}</div>${chosen?'<div class="feature-sub">'+(state.roster[String(chosen.team_id)]||[]).map(esc).join(' · ')+'</div>':''}</div>`;return}
// Screen only receives already-published numbers. No draft access, no hidden score leaks.
const phase=scene==='green'?'green':scene==='blue'?'blue':scene==='red'?'red':'';
const showGreen=(state.published_phases||[]).includes('green');const showBlue=(state.published_phases||[]).includes('blue');const showRed=(state.published_phases||[]).includes('red');const showSecret=(state.revealed_slots||[]).length>0;const showVotes=state.votes_published;
const heads=['','КОМАНДА',showGreen?'GREEN':'—',showBlue?'BLUE':'—',showRed?'RED':'—',showSecret?'SECRET':'—',showVotes?'ГОЛОСА':'—','ИТОГО'];
const captainMap=new Map((state.captains||[]).map(x=>[x.team_id,x]));
const entries=rows.map(r=>{const cap=captainMap.get(r.team_id);return `<div class="rank-row"><span class="place">${r.place===1?'★ ':''}${r.place}</span><span class="name">${cap?avatar(cap.player_id,cap.has_photo):''}${esc(r.name)}${r.tied?' (НИЧЬЯ)':''}</span><span class="points">${showGreen?fmt(r.green):'—'}</span><span class="points">${showBlue?fmt(r.blue):'—'}</span><span class="points">${showRed?fmt(r.red):'—'}</span><span class="points">${showSecret?fmt(r.secret):'—'}</span><span class="points votes">${showVotes?fmt(r.votes):'—'}</span><span class="points total">${fmt(r.total)}</span></div>`}).join('');
panel.innerHTML=header(titles[scene],phase)+`<div class="legend">${heads.map(h=>`<span>${h}</span>`).join('')}</div><div class="rank-board" style="--teams:${Math.max(rows.length,1)}">${entries||'<div class="feature-sub">ОЖИДАНИЕ РЕЗУЛЬТАТОВ</div>'}</div><div class="scene-footer">HI, JACK CLUB · 7 НОЯБРЯ 2026</div>`;
}
function accept(payload){if(payload.version===version)return;const fresh=payload.version>version;version=payload.version;last=payload.state;render(last,fresh&&version>0);$('connection').textContent='● ЭФИР · ОБНОВЛЕНО';$('connection').classList.remove('offline')}
async function poll(){try{const r=await fetch('/sochi/api/public/state',{cache:'no-store'});if(!r.ok)throw Error();accept(await r.json());connected=true}catch{if(!connected&&last)render(last,false);$('connection').textContent='● НЕТ СВЯЗИ · ПОСЛЕДНИЙ КАДР';$('connection').classList.add('offline')}}
let source;
try{source=new EventSource('/sochi/api/public/events');source.addEventListener('state',event=>{connected=true;try{accept(JSON.parse(event.data))}catch{}});source.onerror=()=>{$('connection').textContent='● СВЯЗЬ ПРЕРВАНА · ПОСЛЕДНИЙ КАДР';$('connection').classList.add('offline')}}catch{}
setInterval(poll,6000);poll();$('full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
