'use strict';
/* RED STAGE: the summit assault. Ranking = GREEN + BLUE + RED only.
 * Each actual score is server-frozen; no bonus/Jack/vote data is part of this view.
 * A rank-reveal does not change tournament points or move the cable car.
 */
window.RedShow=(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=value=>new Intl.NumberFormat('ru-RU').format(value||0);
  const rankArt=place=>window.SochiRankMascots?.render(place)||'<span>♠</span>';
  const jack=()=>`<div class="gs-jack-animation" aria-label="Валет HI, JACK с мечом">
     <img class="gs-jack-animation-image"
       src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}"
       alt="Анимация Валета с мечом" loading="eager" decoding="async">
     <div class="gs-jack-animation-tagline">ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</div>
   </div>`;
  const route=()=>`<div class="gs-route-markers">${[
    ['START',true],['GREEN ✓',true],['BLUE ✓',true],['RED ✓',true]
  ].map(([text,done])=>`<div class="gs-route-marker ${done?'lit':''}"><i></i><span>${text}</span></div>`).join('')}</div>`;
  function demo(count=11){
    const previous=window.BlueShow.demo(count).demo_ranking;
    const sortedByPrevious=[...previous].sort((a,b)=>a.team_id-b.team_id);
    const finalOrder=count===11?[6,9,11,2,5,1,10,3,8,4,7]:[6,9,2,5,1,10,3,8,4,7];
    const stagePlace=new Map(finalOrder.map((teamId,index)=>[teamId,index+1]));
    const rows=sortedByPrevious.map(old=>{
      const red_place=stagePlace.get(old.team_id);
      const red=130000-10000*(red_place-1);
      return {...old,red_place,red,total:old.total+red,
              blue_place:old.place};
    });
    rows.sort((a,b)=>b.total-a.total||a.team_id-b.team_id);
    rows.forEach((r,i)=>{
      r.place=i>0&&r.total===rows[i-1].total?rows[i-1].place:i+1;
      r.move=r.blue_place-r.place;
    });
    return {count,step:0,max_step:count+1,demo_ranking:rows,revealed:[]};
  }
  function frame(data,step){
    const ranking=data.demo_ranking||data.revealed||[];
    const count=Number(data.count)||ranking.length;
    const next=Math.max(0,Math.min(count+1,Number(step)||0));
    const revealed=data.demo_ranking?[...ranking].reverse().slice(0,Math.min(next,count)):ranking;
    return {count,step:next,max_step:count+1,revealed};
  }
  function placeCell(row,finishOrder=false){
    return `<div class="rs-list-row ${row.place<=3?'rs-podium-'+row.place:''}">
       <span class="rs-list-icon">${rankArt(row.place)}</span>
       <span class="rs-list-place">${row.place}</span>
       <span class="rs-list-name">${esc(row.name)}</span>
       <span class="rs-list-shift">#${row.blue_place} → #${row.place}</span>
       <span class="rs-list-red">${finishOrder?"#"+row.red_place:fmt(row.red)}</span>
       <span class="rs-list-total">${finishOrder?(row.place===1?"ЧЕМПИОН":"ВЫБЫЛ"):fmt(row.total)}</span>
    </div>`;
  }
  function render(host,data){
    const count=Number(data.count)||10;
    const step=Math.max(0,Math.min(count+1,Number(data.step)||0));
    const intro=step===0;
    const board=step===count+1;
    const rows=data.revealed||[];
    const finishOrder=!!data.finish_order;
    const protagonist=rows.length?rows[rows.length-1]:null;
    const leader=protagonist?.place===1;
    const converted=rows.some(r=>r.base_points!=null&&r.base_points!==r.chip_net);
    const banner=intro?'ФИНАЛЬНЫЙ<br><em>ШТУРМ</em>':board?'РЕЙТИНГ<br><em>RED</em>':'ШТУРМ<br><em>ВЕРШИНЫ</em>';
    host.className='scene green-show-stage red-show-stage';
    host.innerHTML=`<div class="green-experience red-experience rs-${intro?'intro':board?'board':leader?'champion':'reveal'}" data-step="${step}">
      ${window.GreenShow.alpineArt('red')}
      <div class="gs-atmosphere"></div>
      <header class="gs-header">
        <div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt=""><div>
          <small>HI, JACK CLUB · 07.11.2026</small>
          <strong>HI, JACK <em>— HI, SOCHI</em></strong>
        </div></div>
        <div class="gs-step-label"><span class="gs-live-dot"></span> STAGE 03 / RED</div>
      </header>
      <div class="gs-content">
        <div class="gs-main">
          <div class="gs-kicker">ПУТЬ К ВЕРШИНЕ / ЭТАП 03</div>
          <h1 class="gs-title">${banner}</h1>
          <div class="gs-section-rule"></div>
          ${intro?
            `<div class="rs-intro-copy">Три этапа. Одна вершина.<br>${finishOrder?'Победитель RED — чемпион всего турнира. <strong>Выбывание капитана закрепляет итоговое место команды.</strong>':'Места RED определены — <strong>но борьба за общий рейтинг продолжается.</strong>'}</div>
               <div class="rs-intro-notice">RED ЗАВЕРШЁН · НАЧИНАЕМ РАСКРЫТИЕ</div>
               <div class="rs-unrevealed">РЕЗУЛЬТАТЫ ЕЩЁ НЕ ОТКРЫТЫ</div>`:
            board?
              `<div class="rs-list-head"><span></span><span>№</span><span>КОМАНДА</span><span>К BLUE</span><span>${finishOrder?'ФИНИШ':'RED'}</span><span>${finishOrder?'СТАТУС':'ИТОГО'}</span></div>
                <div class="rs-list" style="--rank-count:${count}">${[...rows].sort((a,b)=>a.place-b.place||b.total-a.total||a.team_id-b.team_id).map(row=>placeCell(row,finishOrder)).join('')}</div>
                <div class="rs-afterward">${finishOrder?'МЕСТА ОПРЕДЕЛИЛ RED · ДАЛЕЕ НАГРАЖДЕНИЕ':'ВПЕРЕДИ — SECRET JACK И ГОЛОСОВАНИЕ · ИТОГИ ЕЩЁ МОГУТ ИЗМЕНИТЬСЯ'}</div>`:
              `<div class="rs-reveal-kicker">${finishOrder?(leader?'ПОБЕДИТЕЛЬ ФИНАЛЬНОГО СТОЛА':'МЕСТО ПО ВЫБЫВАНИЮ'):leader?'ЛИДЕР ПОСЛЕ ТРЁХ ЭТАПОВ':'НОВАЯ ПОЗИЦИЯ В ОБЩЕМ РЕЙТИНГЕ'}</div>
               <div class="rs-hero">
                 <span class="rs-hero-mascot">${rankArt(protagonist?.place)}</span>
                 <span class="rs-hero-place">${protagonist?.place||'—'}<small>МЕСТО</small></span>
                 <div class="rs-hero-detail"><div class="rs-hero-name">${esc(protagonist?.name||'')}</div>
                   <div class="rs-hero-shift">BLUE #${protagonist?.blue_place||'—'} → RED #${protagonist?.place||'—'}</div>
                 </div>
               </div>
               <div class="rs-score-panels">
                  <div><small>МЕСТО В RED-ТУРЕ</small><strong>#${protagonist?.red_place||'—'}</strong></div>
                  <div><small>${finishOrder?'ФИНИШ RED':'ОЧКИ RED'}</small><strong>${finishOrder?'#'+protagonist?.red_place:fmt(protagonist?.red)}</strong></div>
                  <div class="rs-cumulative"><small>${finishOrder?'ИТОГОВОЕ МЕСТО':converted?'ОЧКИ BLUE + RED':'GREEN + BLUE + RED'}</small><strong>${finishOrder?'#'+protagonist?.place:fmt(protagonist?.total)}</strong></div>
               </div>
               <div class="gs-reveal-counter">РАСКРЫТО: ${Math.min(count,rows.length)} / ${count}</div>`}
        </div>
        <aside class="gs-side">
          ${jack()}
          <div class="gs-route">${route()}</div>
          <div class="gs-side-bottom"><b>03</b><span>RED<br>SUMMIT CAMP</span><i>↗</i></div>
        </aside>
      </div>
      <footer class="gs-footer"><span>RED / ${intro?'ФИНАЛЬНЫЙ ШТУРМ':board?'ОБЩИЙ РЕЙТИНГ':'РАСКРЫТИЕ МЕСТ'}</span>
        <span>${board?(finishOrder?'ДАЛЬШЕ — НАГРАЖДЕНИЕ':'ДАЛЬШЕ — SECRET JACK'):'ВЕРШИНА БЛИЖЕ, ЧЕМ КАЖЕТСЯ'}</span><span>${step} / ${count+1}</span>
      </footer>
    </div>`;
  }
  return {demo,frame,render};
})();
