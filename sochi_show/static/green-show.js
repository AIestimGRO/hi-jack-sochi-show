'use strict';
/* Visual-only GREEN scene. Never fetches secret admin data or changes scores.
   render() accepts a deliberately filtered, published frame from the server. */
window.GreenShow=(()=>{
  const names=[
    'Чуйка VS Диапазоны','Блефую, сучки','Ставлю карлика',
    'All-in и подомам','Ривер ленд','Творческая',
    'Мам, это спорт','Гребанный туз','Паса не имеем',
    'Я в раздаче','Fuck дилеру'
  ];
  const demoScores=[219000,184000,153000,272000,247000,167000,207000,194000,301000,228000,177000];
  const fmt=x=>new Intl.NumberFormat('ru-RU').format(x||0);
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function demo(count=11){
    const ranked=names.slice(0,count).map((name,i)=>({team_id:i+1,name,green:demoScores[i],total:demoScores[i]}))
      .sort((a,b)=>b.green-a.green||a.team_id-b.team_id)
      .map((t,i)=>({...t,place:i+1}));
    return {count,step:0,max_step:count+2,revealed:[],demo_ranking:ranked};
  }
  function frame(data,step){
    const all=data.demo_ranking||data.revealed||[];
    const count=Number(data.count||all.length);
    const n=Math.max(0,Math.min(count+2,Number(step)));
    const visible=data.demo_ranking?[...all].reverse().slice(0,Math.min(n,count)):all;
    return {count,step:n,max_step:count+2,revealed:visible};
  }
  function alpineArt(){
    return `<svg class="alpine-art" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="alpineSky" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0d464d"/><stop offset=".43" stop-color="#347773"/><stop offset=".75" stop-color="#b0b9a5"/><stop offset="1" stop-color="#e2b17b"/></linearGradient>
        <linearGradient id="alpineFar" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#c5c8b9"/><stop offset="1" stop-color="#486d6b"/></linearGradient>
        <linearGradient id="alpineNear" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#2a5961"/><stop offset=".65" stop-color="#20494d"/><stop offset="1" stop-color="#172a33"/></linearGradient>
        <linearGradient id="alpineBurgundy" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#965059"/><stop offset="1" stop-color="#3a3447"/></linearGradient>
        <radialGradient id="alpineGlow"><stop stop-color="#ffd39d" stop-opacity=".86"/><stop offset=".42" stop-color="#eab884" stop-opacity=".29"/><stop offset="1" stop-color="#efc997" stop-opacity="0"/></radialGradient>
        <filter id="alpineBlur"><feGaussianBlur stdDeviation="38"/></filter>
      </defs>
      <rect width="1920" height="1080" fill="url(#alpineSky)"/>
      <circle cx="1470" cy="205" r="340" fill="url(#alpineGlow)"/>
      <path d="M0 745 L155 640 280 697 430 516 561 669 744 418 902 612 1072 372 1222 558 1430 205 1645 520 1790 395 1920 540 1920 1080H0Z" fill="url(#alpineFar)" opacity=".86"/>
      <path d="M1358 309l72-104 91 113-56-29-35-52-25 56zM1043 420l29-48 40 67-27-15-13-25-12 22zM704 474l40-56 48 81-34-18-14-26-17 27z" fill="#f6e7d3" opacity=".82"/>
      <path d="M-80 850 L170 770 380 805 630 644 745 718 940 583 1116 710 1305 498 1460 654 1702 460 1980 740 2000 1080H-80Z" fill="url(#alpineBurgundy)" opacity=".6"/>
      <path d="M0 918 L170 830 335 875 512 760 705 902 858 744 1045 865 1278 654 1488 856 1690 721 1920 840 1920 1080H0Z" fill="url(#alpineNear)"/>
      <path d="M0 990 C380 916 536 1118 823 971 S1423 1015 1920 932L1920 1080H0Z" fill="#153941" opacity=".78"/>
      <path d="M850 1070 C978 888 1050 911 1155 804 S1308 642 1432 456" fill="none" stroke="#f2b77e" stroke-width="5" stroke-dasharray="13 16" opacity=".62"/>
      <path d="M850 1070 C978 888 1050 911 1155 804 S1308 642 1432 456" fill="none" stroke="#ffe6c6" stroke-width="1.6" opacity=".8"/>
      <circle cx="1432" cy="456" r="9" fill="#fff0d1"/><circle cx="1155" cy="804" r="8" fill="#ffcd93"/><circle cx="850" cy="1070" r="8" fill="#ffcd93"/>
      <path d="M1140 285L1780 440" stroke="#d5e3d7" stroke-width="2.5" opacity=".54"/>
      <g transform="translate(1515 372) rotate(14)"><path d="M0-8v45" stroke="#ded9c4" stroke-width="4"/><path d="M-40 32h80l-7 51h-66Z" fill="#823f50" stroke="#e3c6aa" stroke-width="3"/><rect x="-26" y="44" width="21" height="20" rx="3" fill="#a5c6bc"/><rect x="3" y="44" width="21" height="20" rx="3" fill="#a5c6bc"/></g>
      <g transform="translate(1780 460) rotate(14) scale(.7)"><path d="M0-8v45" stroke="#ded9c4" stroke-width="4"/><path d="M-40 32h80l-7 51h-66Z" fill="#7e8d54" stroke="#e3c6aa" stroke-width="3"/></g>
      <g opacity=".2" stroke="#fff6e5" fill="none"><path d="M-30 860Q510 600 720 730T1460 470"/><path d="M90 975Q490 740 760 800T1660 655"/></g>
    </svg>`;
  }
  function progressMarkup(step,max){
    const stops=[['START',0],['GREEN',1],['SUMMIT',max-1],['BOARD',max]];
    return `<div class="gs-route-markers">${stops.map(([label,val])=>`<div class="gs-route-marker ${step>=val?'lit':''}"><i></i><span>${label}</span></div>`).join('')}</div>`;
  }
  function card(r,small=false){
    return `<div class="gs-team-tile ${r.place<=3?'gs-podium-rank gs-podium-'+r.place:''} ${small?'gs-tile-small':''}">
      <div class="gs-team-place">${r.place}<span>МЕСТО</span></div>
      <div class="gs-team-name">${esc(r.name)}</div>
      <div class="gs-team-score">${fmt(r.green)}<span>ОЧКОВ</span></div>
    </div>`;
  }
  function render(host,data){
    const n=data.count||10, step=Math.max(0,Math.min(n+2,data.step||0));
    const shown=data.revealed||[];
    const latest=shown.length?shown[shown.length-1]:null;
    const isIntro=step===0;
    const leader=step===n+1;
    const board=step===n+2;
    const top=latest&&latest.place<=3;
    const mode=isIntro?'intro':leader?'summit':board?'overview':top?'top':'reveal';
    const ordinal=step===0?'ПЕРВАЯ ВЫСОТА':step<=n?'ОТКРЫВАЕМ ПОЗИЦИИ':leader?'ЛИДЕР GREEN':'ИТОГИ GREEN';
    const secondary=isIntro?'ПУТЬ К ВЕРШИНЕ НАЧИНАЕТСЯ':leader?'ВПЕРЕДИ ЕЩЁ ВОСХОЖДЕНИЕ':'ПЕРВЫЙ ЭТАП ПРОЙДЕН';
    const lastThree=shown.filter(r=>r.place<=3).sort((a,b)=>a.place-b.place);
    host.className='scene green-show-stage';
    host.innerHTML=`<div class="green-experience gs-${mode}" data-step="${step}">
      ${alpineArt()}
      <div class="gs-atmosphere"></div>
      <header class="gs-header"><div class="gs-brand"><img src="/sochi/static/hi-jack-logo.svg" alt=""><div><small>HI, JACK CLUB · 07.11.2026</small><strong>HI, JACK <em>— HI, SOCHI</em></strong></div></div><div class="gs-step-label"><span class="gs-live-dot"></span> STAGE 01 / GREEN</div></header>
      <div class="gs-content">
        <div class="gs-main">
          <div class="gs-kicker">ПУТЬ К ВЕРШИНЕ / ЭТАП 01</div>
          <h1 class="gs-title">${isIntro?'ПЕРВАЯ<br><em>ВЫСОТА</em>':board?'РЕЗУЛЬТАТЫ<br><em>GREEN</em>':leader?'НА ВЕРШИНЕ<br><em>GREEN</em>':'ВОСХОЖДЕНИЕ<br><em>ПРОДОЛЖАЕТСЯ</em>'}</h1>
          <div class="gs-section-rule"></div>
          ${isIntro?`<div class="gs-intro-text">Первые итоги командного восхождения.<br>Каждая фишка — ещё один шаг к Сочи.</div><div class="gs-intro-cta">11 КОМАНД · ОДНА ВЕРШИНА</div>`.replace('11 КОМАНД',n+' КОМАНД')
           :board?`<div class="gs-overview"><div class="gs-overview-cards">${[...shown].sort((a,b)=>a.place-b.place).map(r=>card(r,true)).join('')}</div></div>`
           :`<div class="gs-reveal-label">${leader?'ЛИДЕР ПЕРВОГО ЭТАПА':latest&&latest.place<=3?'НА ПОДИУМЕ':'ОТКРЫТО МЕСТО'}</div>
              <div class="gs-hero"><span class="gs-hero-place">${latest?.place||'—'}<small>МЕСТО</small></span><div class="gs-hero-team"><div class="gs-hero-name">${esc(latest?.name||'')}</div><div class="gs-hero-points">${fmt(latest?.green)} <span>ОЧКОВ</span></div></div></div>
              ${lastThree.length&&top||leader?`<div class="gs-top3-mini">${lastThree.map(r=>`<div class="${r.place===1?'champion':''}"><small>#${r.place}</small><strong>${esc(r.name)}</strong></div>`).join('')}</div>`:''}
              <div class="gs-reveal-counter">РАСКРЫТО: ${Math.min(n,shown.length)} / ${n}</div>`}
        </div>
        <aside class="gs-side"><div class="gs-mountain-badge"><span>♠</span><strong>HI,<br>SOCHI</strong><small>ВЫСОТА · ВОЛЯ · ПОБЕДА</small></div><div class="gs-route">${progressMarkup(step,n+2)}</div><div class="gs-side-bottom"><b>01</b><span>GREEN<br>BASE CAMP</span><i>↗</i></div></aside>
      </div>
      <footer class="gs-footer"><span>GREEN / ${esc(ordinal)}</span><span>${esc(secondary)}</span><span>${step} / ${n+2}</span></footer>
    </div>`;
  }
  return {render,demo,frame};
})();
