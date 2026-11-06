'use strict';
/* HI, JACK — HI, SOCHI / CAPTAINS
 * A premium expedition roster, replacing the old black unstyled grid.
 * Only the already-published state.captains and state.teams may be shown.
 */
window.CaptainShow=(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const jsImage=id=>{
    const num=Number(id);
    return Number.isSafeInteger(num)&&num>0?'/sochi/api/public/photo/'+num:'';
  };
  const jack=()=>`<div class="gs-jack-animation" aria-label="Анимированный Валет с мечом">
    <img class="gs-jack-animation-image" alt="Валет с мечом HI, JACK" loading="eager"
      src="${window.JackSwordGifB64?'data:image/gif;base64,'+window.JackSwordGifB64:'/sochi/static/hi-jack-logo.svg'}">
    <div class="gs-jack-animation-tagline">ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</div>
  </div>`;
  const route=()=>'<div class="gs-route-markers">'+[
      ['START ✓',true],['GREEN ✓',true],['BLUE ✓',true],['RED',false],['SUMMIT',false]
    ].map(([name,lit])=>`<div class="gs-route-marker ${lit?'lit':''}"><i></i><span>${name}</span></div>`).join('')+'</div>';
  function demo(count=10,all=false){
    const names=['Чуйка VS Диапазоны','Блефую, сучки','Ставлю карлика',
      'All-in и подомам','Ривер ленд','Творческая','Мам, это спорт',
      'Гребанный туз','Паса не имеем','Я в раздаче','Fuck дилеру'];
    const teams=Object.fromEntries(names.slice(0,count).map((name,i)=>[i+1,name]));
    const demoNames=['Миша','Олег','Артём','Пика','Катя','Илья','Юля','Денис','Игорь','Саша','Женя'];
    const captains=Object.keys(teams).map(key=>{
      const id=Number(key);
      const picked=all||id===1||id===4;
      return {team_id:id,name:picked?demoNames[id-1]:'Капитан не выбран',
        player_id:picked?id+100:null,has_photo:false};
    });
    return {team_count:count,teams,captains};
  }
  const captainTile=(id,name,entry)=>{
    const hasCaptain=!!entry?.player_id&&entry?.name&&entry.name!=='Капитан не выбран';
    const url=hasCaptain&&entry.has_photo?jsImage(entry.player_id):'';
    const image=url?`<img class="cs-portrait-photo" src="${url}" alt="Фото капитана команды №${id}" loading="eager">`:
      `<div class="cs-portrait-symbol" role="img" aria-label="${hasCaptain?'Фото не загружено':'Капитан не назначен'}">♠</div>`;
    return `<article class="cs-tile ${hasCaptain?'cs-assigned':'cs-awaiting'}" aria-label="Команда №${id}: ${esc(name)}">
      <div class="cs-tile-top"><span class="cs-team-index">ЭКСПЕДИЦИЯ ${String(id).padStart(2,'0')}</span><span class="cs-tile-spade">♠</span></div>
      <div class="cs-tile-center">
        <div class="cs-portrait">${image}</div>
        <div class="cs-captain-line"><span class="cs-role">${hasCaptain?'КАПИТАН':'КОМАНДА'}</span>
          ${hasCaptain?`<strong class="cs-captain-name">${esc(entry.name)}</strong>`:
            '<strong class="cs-captain-pending">КАПИТАН ОЖИДАЕТСЯ</strong>'}
        </div>
      </div>
      <div class="cs-team-name">${esc(name)}</div>
    </article>`;
  };
  function render(host,data){
    const teams=data?.teams||{};
    const roster=Object.entries(teams).map(([id,name])=>[Number(id),name])
      .filter(([id])=>Number.isSafeInteger(id)&&id>0)
      .sort((a,b)=>a[0]-b[0]);
    const captainMap=new Map((data?.captains||[]).map(c=>[Number(c.team_id),c]));
    const total=roster.length;
    const assigned=roster.filter(([id])=>{
      const c=captainMap.get(id);
      return c?.player_id&&c.name&&c.name!=='Капитан не выбран';
    }).length;
    const columns=total>10?6:5;
    host.className='scene green-show-stage captain-show-stage';
    host.innerHTML=`<div class="green-experience captain-experience" data-total="${total}" style="--captain-columns:${columns}">
      ${window.GreenShow.alpineArt('blue')}
      <div class="gs-atmosphere"></div>
      <header class="gs-header">
        <div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt="">
          <div><small>HI, JACK CLUB · 07.11.2026</small>
          <strong>HI, JACK <em>— HI, SOCHI</em></strong></div></div>
        <div class="gs-step-label"><span class="gs-live-dot"></span> EXPEDITION / CAPTAINS</div>
      </header>
      <div class="gs-content">
        <section class="gs-main">
          <div class="gs-kicker">ПУТЬ К ВЕРШИНЕ / КОМАНДЫ И ЛИДЕРЫ</div>
          <h1 class="gs-title">КАПИТАНЫ <em>ЭКСПЕДИЦИЙ</em></h1>
          <div class="gs-section-rule"></div>
          <div class="cs-subline"><strong>${total} КОМАНД</strong><span>ОДНА ЦЕЛЬ — ВЕРШИНА</span></div>
          <div class="cs-tiles" style="--captain-count:${total}">${roster.map(([id,name])=>captainTile(id,name,captainMap.get(id))).join('')}</div>
          <div class="cs-footnote">ЛИДЕРЫ ОПРЕДЕЛЯЮТ МАРШРУТ · ${assigned} ИЗ ${total} КАПИТАНОВ НАЗНАЧЕНО</div>
        </section>
        <aside class="gs-side">
          ${jack()}
          <div class="gs-route">${route()}</div>
          <div class="gs-side-bottom"><b>♠</b><span>CAPTAINS<br>EXPEDITION</span><i>↗</i></div>
        </aside>
      </div>
      <footer class="gs-footer"><span>HI, JACK — HI, SOCHI / КАПИТАНЫ</span>
        <span>ЗАЛЕТАЙ · ЗАЦЕПИСЬ · ЗАВОЮЙ</span><span>${total} КОМАНД</span></footer>
    </div>`;
  }
  return {demo,render};
})();
