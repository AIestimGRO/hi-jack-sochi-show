'use strict';
/* SECRET JACK cinematic: only published, confirmed reveals are shown.
 * The server issues the identities one at a time; client never holds draft data.
 */
window.SecretShow=(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const teams=data=>data.teams||{};
  const teamName=(data,id)=>esc(teams(data)[String(id)]||('Команда №'+(id||'—')));
  const portrait=s=>s?.has_photo&&Number.isSafeInteger(Number(s.player_id))&&Number(s.player_id)>0
    ?'<img class="ss-portrait-photo" src="/sochi/api/public/photo/'+Number(s.player_id)+'" alt="Фото раскрытого Валета" loading="eager">'
    :'<div class="ss-portrait-fallback" role="img" aria-label="Портрет не загружен"><span>♠</span><small>SECRET JACK</small></div>';
  const animatedJack=()=>`<div class="gs-jack-animation" aria-label="Анимированный Валет с мечом">
    <img class="gs-jack-animation-image" alt="Валет HI JACK с мечом" loading="eager"
      src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}">
    <div class="gs-jack-animation-tagline">ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</div>
  </div>`;
  const route=()=>'<div class="gs-route-markers">'+[
    ['GREEN ✓',true],['BLUE ✓',true],['RED ✓',true],['JACK',true]
  ].map(([x,done])=>`<div class="gs-route-marker ${done?'lit':''}"><i></i><span>${x}</span></div>`).join('')+'</div>';
  function demo(){
    const t={'1':'Чуйка VS Диапазоны','2':'Блефую, сучки','3':'Ривер ленд','4':'Мам, это спорт','5':'Паса не имеем','6':'Творческая'};
    const cards=[
      {slot:1,player_id:101,name:'Демо-игрок А',jack_team_id:3,
       knockout_team_id:2,knockout_name:'Демо-игрок Б',confirmed:true,has_photo:false},
      {slot:2,player_id:102,name:'Демо-игрок В',jack_team_id:5,
       knockout_team_id:null,knockout_name:null,confirmed:false,has_photo:false},
      {slot:3,player_id:103,name:'Демо-игрок Г',jack_team_id:1,
       knockout_team_id:4,knockout_name:'Демо-игрок Д',confirmed:true,has_photo:false}
    ];
    return {teams:t,all_demo_cards:cards,step:0,revealed:[],revealed_count:3};
  }
  function frame(demoData,step){
    const n=Math.max(0,Math.min(4,Number(step)||0));
    const full=demoData.all_demo_cards||[];
    return {teams:demoData.teams,step:n,summary:n===4,
      revealed_count:full.length,revealed:full.slice(0,Math.min(n,3)),
      max_step:4};
  }
  const cardState=(slot,step,shown)=>{
    if(slot===step&&step<=3)return 'current';
    if(shown.some(s=>s.slot===slot))return 'opened';
    return 'locked';
  };
  function seals(step,shown){
    return `<div class="ss-seals" aria-label="Последовательность раскрытия">${[1,2,3].map(slot=>{
      const state=cardState(slot,step,shown);
      return `<div class="ss-seal ss-${state}">
        <span>${state==='locked'?'♠':'♛'}</span>
        <strong>№ ${slot}</strong>
        <small>${state==='locked'?'СЕКРЕТ':state==='current'?'ОТКРЫТ':'РАСКРЫТ'}</small>
      </div>`;
    }).join('')}</div>`;
  }
  function summaryCard(data,card){
    const receiver=card.confirmed?teamName(data,card.knockout_team_id):'ВЫБИВАНИЕ НЕ ПОДТВЕРЖДЕНО';
    return `<div class="ss-summary-card">
      <div class="ss-summary-symbol">♛</div>
      <div class="ss-summary-slot">SECRET JACK ${card.slot}</div>
      <div class="ss-summary-name">${esc(card.name)}</div>
      <div class="ss-summary-team">${teamName(data,card.jack_team_id)}</div>
      <div class="ss-summary-divider"></div>
      <div class="ss-summary-result ${card.confirmed?'bounty':'safe'}">
        <strong>${card.confirmed?'+10 000':'0'}</strong>
        <small>${card.confirmed?'БОНУС ЗА ВЫБИВАНИЕ':'НЕ ВЫБИТ'}</small>
      </div>
      <div class="ss-summary-receiver">${receiver}</div>
    </div>`;
  }
  function render(host,data){
    const step=Math.max(0,Math.min(4,Number(data?.step)||0));
    const revealed=data?.revealed||[];
    const summary=step===4&&revealed.length===3;
    const active=step>=1&&step<=3?revealed.find(s=>s.slot===step):null;
    const counted=revealed.filter(s=>s.confirmed).length;
    const title=step===0?'ТАЙНЫЕ<br><em>ВАЛЕТЫ</em>':summary?'ТРИ<br><em>ВАЛЕТА</em>':'МАСКИ<br><em>СБРОШЕНЫ</em>';
    host.className='scene green-show-stage secret-show-stage';
    host.innerHTML=`<div class="green-experience secret-experience ss-${step===0?'intro':summary?'summary':'reveal'}" data-step="${step}">
      ${window.GreenShow.alpineArt('red')}
      <div class="gs-atmosphere"></div>
      <header class="gs-header">
        <div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt="">
          <div><small>HI, JACK CLUB · 07.11.2026</small><strong>HI, JACK <em>— HI, SOCHI</em></strong></div>
        </div>
        <div class="gs-step-label"><span class="gs-live-dot"></span> SECRET JACK / 03</div>
      </header>
      <div class="gs-content"><div class="gs-main">
        <div class="gs-kicker">ПОСЛЕ RED / ТАЙНОЕ РАСКРЫТИЕ</div>
        <h1 class="gs-title">${title}</h1>
        <div class="gs-section-rule"></div>
        ${step===0?
          `<div class="ss-intro-text">Три игрока. Три скрытых роли.<br>
            <strong>Кто получит бонус за выбивание SECRET JACK?</strong></div>
            ${seals(step,revealed)}
            <div class="ss-cinematic-note">ИМЕНА РАСКРЫВАЕТ ТОЛЬКО ВЕДУЩИЙ</div>`:
          summary?
          `<div class="ss-summary-header">ТРИ РОЛИ РАСКРЫТЫ · НАЧИСЛЕННЫЕ БОНУСЫ</div>
            <div class="ss-summary-grid">${revealed.slice(0,3).map(s=>summaryCard(data,s)).join('')}</div>
            <div class="ss-summary-bottom"><strong>ВСЕГО БОНУСОВ: ${new Intl.NumberFormat('ru-RU').format(counted*10000)}</strong>
              <span>ДАЛЬШЕ — ГОЛОСОВАНИЕ КАПИТАНОВ</span></div>`:
          active?
          `<div class="ss-current-label">SECRET JACK № ${active.slot} / 3</div>
            <div class="ss-reveal-layout">
              <div class="ss-photo-frame">${portrait(active)}
                <span class="ss-photo-corner ss-tl"></span><span class="ss-photo-corner ss-tr"></span>
                <span class="ss-photo-corner ss-bl"></span><span class="ss-photo-corner ss-br"></span>
              </div>
              <div class="ss-reveal-info">
                <div class="ss-player-title">СЕКРЕТНЫЙ ВАЛЕТ</div>
                <div class="ss-player-name">${esc(active.name)}</div>
                <div class="ss-team-label">ИГРАЛ ЗА КОМАНДУ</div>
                <div class="ss-team-name">${teamName(data,active.jack_team_id)}</div>
                <div class="ss-result-block ${active.confirmed?'bounty':'safe'}">
                  ${active.confirmed?
                    `<strong>+10 000 ОЧКОВ</strong><span>БОНУС КОМАНДЕ</span>
                       <b>${teamName(data,active.knockout_team_id)}</b>
                       <small>ВЫБИЛ: ${esc(active.knockout_name||'игрок не указан')}</small>`:
                    `<strong>SECRET JACK ВЫСТОЯЛ</strong><span>ВЫБИВАНИЕ НЕ ПОДТВЕРЖДЕНО</span>
                       <b>БОНУС НЕ НАЧИСЛЕН</b>`}
                </div>
              </div>
            </div>
            ${seals(step,revealed)}`:
          `<div class="ss-intro-text">ОЖИДАЕМ РАСКРЫТИЯ…</div>`}
      </div>
      <aside class="gs-side">
        ${animatedJack()}
        <div class="gs-route">${route()}</div>
        <div class="gs-side-bottom"><b>♠</b><span>SECRET<br>JACK SHOW</span><i>✦</i></div>
      </aside></div>
      <footer class="gs-footer"><span>SECRET JACK / ${step===0?'ТАЙНА':summary?'ИТОГИ':'РАСКРЫТИЕ № '+step}</span>
        <span>${summary?'ВПЕРЕДИ — ГОЛОСА КАПИТАНОВ':'БОНУСЫ НАЧИСЛЯЮТСЯ ТОЛЬКО ЗА ВЫБИВАНИЕ'}</span><span>${step} / 4</span>
      </footer></div>`;
  }
  return {demo,frame,render};
})();
