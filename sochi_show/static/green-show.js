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
  // The single cabin marks GREEN completion, NOT the rank currently revealed.
  // It always stays at the first reached station; only future tournament phases move it.
  const cable={start:[730,790],control1:[930,652],control2:[1170,427],end:[1440,245]};
  function cablePoint(t){
    const u=1-t,p=cable;
    return [
      u*u*u*p.start[0]+3*u*u*t*p.control1[0]+3*u*t*t*p.control2[0]+t*t*t*p.end[0],
      u*u*u*p.start[1]+3*u*u*t*p.control1[1]+3*u*t*t*p.control2[1]+t*t*t*p.end[1]
    ];
  }
  function alpineArt(){
    const [cabinX,cabinY]=cablePoint(.28);
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
      <!-- One actual cable. START is its lower end; the cabin is attached to it. -->
      <path id="sochi-cable" d="M730 790 C930 652 1170 427 1440 245" fill="none" stroke="#102c37" stroke-width="8" opacity=".45"/>
      <path d="M730 790 C930 652 1170 427 1440 245" fill="none" stroke="#e8d5b5" stroke-width="3.2" opacity=".92"/>
      <circle class="alpine-start-halo" cx="730" cy="790" r="27" fill="#f1c28e" opacity=".19"/>
      <circle cx="730" cy="790" r="10" fill="#f7d3a1" stroke="#244e54" stroke-width="4"/>
      <circle cx="1440" cy="245" r="10" fill="#fff0d1" stroke="#36585a" stroke-width="4"/>
      <text x="677" y="847" fill="#fff0da" font-size="23" font-weight="850" letter-spacing="4">START</text>
      <!-- GREEN is the first reached station, fixed during the entire ranking reveal. -->
      <circle cx="${cabinX.toFixed(1)}" cy="${cabinY.toFixed(1)}" r="23" fill="#c9d895" opacity=".28"/>
      <circle cx="${cabinX.toFixed(1)}" cy="${cabinY.toFixed(1)}" r="11" fill="#dce6ad" stroke="#32565b" stroke-width="3"/>
      <text x="${(cabinX+67).toFixed(1)}" y="${(cabinY+45).toFixed(1)}" fill="#eff8d1" font-size="23" font-weight="900" letter-spacing="3">GREEN ✓</text>
      <g class="alpine-cabin" transform="translate(${cabinX.toFixed(1)} ${cabinY.toFixed(1)})">
        <circle cx="0" cy="0" r="7" fill="#f8e5c8" stroke="#264950" stroke-width="2"/>
        <path d="M0 4v45" fill="none" stroke="#f0ddbe" stroke-width="5"/>
        <path d="M-47 49h94l-8 62h-78Z" fill="#843d50" stroke="#f2c08c" stroke-width="4"/>
        <path d="M-42 55h84l-7 43h-70Z" fill="#aa5660" opacity=".45"/>
        <rect x="-32" y="60" width="25" height="25" rx="4" fill="#b6d8d3" stroke="#e8c5a5" stroke-width="2"/>
        <rect x="7" y="60" width="25" height="25" rx="4" fill="#b6d8d3" stroke="#e8c5a5" stroke-width="2"/>
        <path d="M-27 107h54" stroke="#e6bb90" stroke-width="4" stroke-linecap="round"/>
      </g>
      <g opacity=".2" stroke="#fff6e5" fill="none"><path d="M-30 860Q510 600 720 730T1460 470"/><path d="M90 975Q490 740 760 800T1660 655"/></g>
    </svg>`;
  }
  function progressMarkup(){
    const stops=[['START',true],['GREEN ✓',true],['SUMMIT',false],['BOARD',false]];
    return `<div class="gs-route-markers">${stops.map(([label,done])=>`<div class="gs-route-marker ${done?'lit':''}"><i></i><span>${label}</span></div>`).join('')}</div>`;
  }
  function rankingRow(r){
    const podium=r.place<=3?' gs-rank-'+r.place:'';
    return `<div class="gs-ranking-row${podium}">
      <div class="gs-ranking-place"><b>${r.place}</b><span>МЕСТО</span></div>
      <div class="gs-ranking-name">${esc(r.name)}</div>
      <div class="gs-ranking-score"><b>${fmt(r.green)}</b><span>ОЧКОВ</span></div>
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
           :board?`<div class="gs-overview"><div class="gs-ranking-list" style="--rank-count:${n}">${[...shown].sort((a,b)=>a.place-b.place||b.green-a.green||a.team_id-b.team_id).map(r=>rankingRow(r)).join('')}</div></div>`
           :`<div class="gs-reveal-label">${leader?'ЛИДЕР ПЕРВОГО ЭТАПА':latest&&latest.place<=3?'НА ПОДИУМЕ':'ОТКРЫТО МЕСТО'}</div>
              <div class="gs-hero"><span class="gs-hero-place">${latest?.place||'—'}<small>МЕСТО</small></span><div class="gs-hero-team"><div class="gs-hero-name">${esc(latest?.name||'')}</div><div class="gs-hero-points">${fmt(latest?.green)} <span>ОЧКОВ</span></div></div></div>
              ${lastThree.length&&top||leader?`<div class="gs-top3-mini">${lastThree.map(r=>`<div class="${r.place===1?'champion':''}"><small>#${r.place}</small><strong>${esc(r.name)}</strong></div>`).join('')}</div>`:''}
              <div class="gs-reveal-counter">РАСКРЫТО: ${Math.min(n,shown.length)} / ${n}</div>`}
        </div>
        <aside class="gs-side"><div class="gs-mountain-badge"><span>♠</span><strong>HI,<br>SOCHI</strong><small>ВЫСОТА · ВОЛЯ · ПОБЕДА</small></div><div class="gs-route">${progressMarkup()}</div><div class="gs-side-bottom"><b>01</b><span>GREEN<br>BASE CAMP</span><i>↗</i></div></aside>
      </div>
      <footer class="gs-footer"><span>GREEN / ${esc(ordinal)}</span><span>${esc(secondary)}</span><span>${step} / ${n+2}</span></footer>
    </div>`;
  }
  return {render,demo,frame};
})();
