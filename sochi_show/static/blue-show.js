'use strict';
/* HI JACK / SOCHI: BLUE — cumulative GREEN+BLUE ranking, reveal by reveal.
 * Public renderer receives only server-filtered already revealed rows.
 * No scores are recalculated on the client during live events.
 */
window.BlueShow=(()=>{
  const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=value=>new Intl.NumberFormat('ru-RU').format(value||0);
  const ranks=count=>Array.from({length:count},(_,i)=>i+1);

  // Synthetic demonstration ONLY. Never used for a real tournament publication.
  function demo(count=11){
    const green=window.GreenShow.demo(count).demo_ranking;
    const greenById=new Map(green.map(r=>[r.team_id,r]));
    const blueDemo=[29000,-32000,115000,86000,-25000,67000,155000,-10000,17000,76000,138000];
    const ranked=green.map(r=>({
      team_id:r.team_id,name:r.name,green:r.green,blue:blueDemo[r.team_id-1],
      total:r.green+blueDemo[r.team_id-1],
      green_place:greenById.get(r.team_id).place
    }));
    ranked.sort((a,b)=>b.total-a.total||a.team_id-b.team_id);
    ranked.forEach((row,index)=>{
      row.place=index&&row.total===ranked[index-1].total?ranked[index-1].place:index+1;
      row.move=row.green_place-row.place;
    });
    return {count,step:0,max_step:count+1,demo_ranking:ranked,revealed:[]};
  }
  function frame(data,step){
    const full=data.demo_ranking||data.revealed||[];
    const count=Number(data.count||full.length);
    const n=Math.max(0,Math.min(count+1,Number(step)||0));
    const revealed=data.demo_ranking?[...full].reverse().slice(0,Math.min(n,count)):full;
    return {count,step:n,max_step:count+1,revealed};
  }
  const rankArt=place=>window.SochiRankMascots?.render(place)||'<span class="gs-rank-symbol">♠</span>';
  const moveDescription=(row)=>{
    if(row.move>0)return {mark:'▲',className:'rise',text:'+'+row.move+' мест',long:'ПОДЪЁМ НА '+row.move+' МЕСТ'};
    if(row.move<0)return {mark:'▼',className:'fall',text:'−'+Math.abs(row.move)+' мест',long:'ПОТЕРЯ '+Math.abs(row.move)+' МЕСТ'};
    return {mark:'—',className:'same',text:'без изменений',long:'ПОЗИЦИЯ СОХРАНЕНА'};
  };
  const jack=()=>`<div class="gs-jack-animation" aria-label="Валет с мечом — фирменная анимация HI, JACK">
    <img class="gs-jack-animation-image" src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}"
      alt="Анимированный Валет HI, JACK с мечом" loading="eager" decoding="async">
    <div class="gs-jack-animation-tagline">БЛЕФ · СТЕК · ОЛЛ-ИН</div>
  </div>`;
  function route(){
    return '<div class="gs-route-markers">'+[
      ['START',true],['GREEN ✓',true],['BLUE ✓',true],['SUMMIT',false]
    ].map(([label,lit])=>`<div class="gs-route-marker ${lit?'lit':''}"><i></i><span>${label}</span></div>`).join('')+'</div>';
  }
  function rankingRow(r){
    const movement=moveDescription(r);
    return `<div class="bs-ranking-row ${r.place<=3?'bs-podium-'+r.place:''}">
       <span class="bs-icon">${rankArt(r.place)}</span>
       <span class="bs-place">${r.place}</span>
       <span class="bs-name">${escapeHTML(r.name)}</span>
       <span class="bs-move ${movement.className}">${movement.mark} ${escapeHTML(movement.text)}</span>
       <span class="bs-blue-points">${fmt(r.blue)}</span>
       <span class="bs-total">${fmt(r.total)}</span>
     </div>`;
  }
  function render(host,data){
    const count=Number(data.count)||10;
    const step=Math.max(0,Math.min(count+1,Number(data.step)||0));
    const intro=step===0,board=step===count+1;
    const visible=data.revealed||[];
    // The last revealed row is the current protagonist, including tied scores.
    const latest=visible.length?visible[visible.length-1]:null;
    const winner=latest?.place===1;
    const movement=latest?moveDescription(latest):null;
    const subtitle=intro?'ВТОРАЯ ВЫСОТА':board?'ПОЛНЫЙ РЕЙТИНГ GREEN + BLUE':'НОВОЕ МЕСТО В ОБЩЕМ РЕЙТИНГЕ';
    const topper=intro?'СМЕНА<br><em>ВЫСОТЫ</em>':board?'РЕЙТИНГ<br><em>BLUE</em>':'ГОНКА ЗА<br><em>ВЕРШИНОЙ</em>';
    host.className='scene green-show-stage blue-show-stage';
    host.innerHTML=`<div class="green-experience blue-experience bs-${intro?'intro':board?'board':winner?'champion':'reveal'}" data-step="${step}">
      ${window.GreenShow.alpineArt('blue')}
      <div class="gs-atmosphere"></div>
      <header class="gs-header">
        <div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt="">
          <div><small>HI, JACK CLUB · 07.11.2026</small><strong>HI, JACK <em>— HI, SOCHI</em></strong></div>
        </div>
        <div class="gs-step-label"><span class="gs-live-dot"></span> STAGE 02 / BLUE</div>
      </header>
      <div class="gs-content">
        <div class="gs-main">
          <div class="gs-kicker">ПУТЬ К ВЕРШИНЕ / ЭТАП 02</div>
          <h1 class="gs-title">${topper}</h1>
          <div class="gs-section-rule"></div>
          ${intro?
            `<div class="bs-intro-copy">Первая высота позади. После BLUE вся борьба — в том, <strong>кто поднялся выше</strong>.</div>
              <div class="bs-intro-footer">НОВЫЕ ПОЗИЦИИ · ${count} КОМАНД</div>`:
            board?
              `<div class="bs-table-head">
                <span></span><span>№</span><span>КОМАНДА</span><span>К GREEN</span><span>ОЧКИ BLUE</span><span>СУММА</span>
              </div>
              <div class="bs-ranking-list" style="--rank-count:${count}">
                ${[...visible].sort((a,b)=>a.place-b.place||b.total-a.total||a.team_id-b.team_id).map(rankingRow).join('')}
              </div>`:
              `<div class="bs-hero-label">${winner?'НОВЫЙ ЛИДЕР ПО ИТОГАМ BLUE':'РАСКРЫВАЕМ МЕСТО'}</div>
                <div class="bs-hero">
                  <span class="bs-hero-icon">${rankArt(latest?.place)}</span>
                  <span class="bs-hero-place">${latest?.place||'—'}<small>МЕСТО</small></span>
                  <div class="bs-hero-right">
                    <div class="bs-hero-name">${escapeHTML(latest?.name||'')}</div>
                    <div class="bs-change-line">
                      <span class="bs-from">GREEN #${latest?.green_place||'—'} → BLUE #${latest?.place||'—'}</span>
                      <strong class="${movement?.className||'same'}">${escapeHTML(movement?.long||'')}</strong>
                    </div>
                  </div>
                </div>
                <div class="bs-score-panels">
                  <div><small>ОЧКИ ЭТАПА BLUE</small><strong>${fmt(latest?.blue)}</strong></div>
                  <div class="bs-cumulative"><small>СУММА GREEN + BLUE</small><strong>${fmt(latest?.total)}</strong></div>
                </div>
                <div class="gs-reveal-counter">РАСКРЫТО: ${Math.min(visible.length,count)} / ${count}</div>`}
        </div>
        <aside class="gs-side">
          ${jack()}
          <div class="gs-route">${route()}</div>
          <div class="gs-side-bottom"><b>02</b><span>BLUE<br>RIDGE CAMP</span><i>↗</i></div>
        </aside>
      </div>
      <footer class="gs-footer"><span>BLUE / ${subtitle}</span><span>ВЫШЕ ТОЛЬКО ФИНАЛ</span><span>${step} / ${count+1}</span></footer>
    </div>`;
  }
  return {render,demo,frame};
})();
