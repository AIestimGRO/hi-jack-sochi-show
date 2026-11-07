'use strict';
let state=null;
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>new Intl.NumberFormat('ru-RU').format(v??0);

/* Progressive disclosure: keep the operator's next task visible without hiding controls permanently. */
const MODULES=[
  ['control-panel','ЭФИР','Пульт проектора','Показывай нужную сцену только когда она опубликована.'],
  ['seating-panel','01','Рассадка','Начни с JSON, числа команд и распределения мест.'],
  ['player-chips-panel','01А','Re-entry / add-on по игрокам','Быстрые кнопки ±1 и командная сумма в таблице №3.'],
  ['teams-panel','02','Игроки и команды','Имена, капитаны, фотографии и публикация команд.'],
  ['scores-panel','03','Результаты GREEN / BLUE / RED','Заполняй этапы последовательно; перед публикацией будет расчёт.'],
  ['secrets-panel','04','Secret Jacks','Три закрытых назначения и поочерёдное раскрытие.'],
  ['votes-panel','05','Голоса команд','Один голос от каждой команды, затем кинематографическое раскрытие.'],
  ['review-panel','06','Рейтинг и протокол','Итоговая проверка, история изменений, CSV.']
];
let guideOpened=false;
function installModuleLayout(){
  for(const [id,number,title,description] of MODULES){
    const panel=$(id);
    if(!panel)continue;
    const module=document.createElement('details');
    module.className='module-accordion';
    module.id='module-'+id;
    const head=document.createElement('summary');
    head.innerHTML='<span class="module-number">'+number+'</span><span class="module-heading"><strong>'+title+'</strong><small>'+description+'</small></span><span class="module-state" id="state-'+id+'">Ожидание</span>';
    panel.before(module);
    module.append(head,panel);
  }
  $('expand-modules').onclick=()=>document.querySelectorAll('.module-accordion').forEach(el=>el.open=true);
  $('collapse-modules').onclick=()=>document.querySelectorAll('.module-accordion').forEach(el=>el.open=false);
  document.querySelectorAll('[data-open-panel]').forEach(a=>a.addEventListener('click',event=>{
    event.preventDefault();
    const dest=$('module-'+a.dataset.openPanel);
    if(!dest)return;
    dest.open=true;
    dest.scrollIntoView({behavior:'smooth',block:'start'});
  }));
}
function updateWorkflow(){
  if(!state)return;
  const pub=state.published||{};
  const phases=pub.published_phases||[];
  const teamTotal=Number(state.team_count||0);
  const teamsDone=teamTotal>0&&Object.keys(pub.teams||{}).length===teamTotal;
  const finalStacksReady=pub.blue_policy?.mode==='final_table' && !!pub.blue_policy?.revealed;
  const steps=[
    teamTotal>0,teamsDone,phases.includes('green'),phases.includes('blue'),
    finalStacksReady,(pub.revealed_slots||[]).length===3,
    !!pub.votes_published,phases.includes('red'),
    ['final','winner'].includes(pub.scene)
  ];
  const prompts=[
    'Шаг 1: выбери 10 или 11 команд и импортируй файл рассадки.',
    'Шаг 2: проверь имена и нажми «Опубликовать все названия».',
    'Шаг 3: заполни GREEN для всех команд и нажми «Опубликовать GREEN».',
    'Шаг 4: заполни BLUE и опубликуй результаты после GREEN.',
    'Шаг 5: утверди и объяви капитанам стеки 100 000–1 000 000 в BLUE → ФИНАЛЬНЫЙ СТОЛ.',
    'Шаг 6: сохрани трёх Secret Jacks и раскрой их по одному.',
    'Шаг 7: запиши голоса и заверши показ голосования на экране.',
    'Шаг 8: после розыгрыша финального стола внеси и опубликуй места RED.',
    'Шаг 9: открой финальную таблицу через пульт эфира.'
  ];
  const done=steps.filter(Boolean).length;
  $('guide-done').textContent=done+' из '+steps.length;
  $('guide-progress-fill').style.width=(done/steps.length*100)+'%';
  $('guide-next').textContent=done===steps.length
    ?'Все этапы опубликованы. Проверь финальный рейтинг и протокол.'
    :prompts[steps.findIndex(x=>!x)];
  const assigned=state.seats.filter(s=>s.player_id).length;
  const badges={
    'control-panel':pub.scene?('Сцена: '+pub.scene.toUpperCase()):'Заставка',
    'seating-panel':teamTotal?(teamTotal+' команд · '+assigned+'/'+teamTotal*3+' игроков'):'Не импортировано',
    'teams-panel':teamsDone?'Названия опубликованы':'Не опубликованы',
    'player-chips-panel': 'Участников: '+assigned+' · живой учёт',
    'scores-panel':phases.length?(phases.join(' / ').toUpperCase()):'Нет результатов',
    'secrets-panel':(pub.revealed_slots||[]).length+'/3 раскрыто',
    'votes-panel':pub.votes_published?'Опубликованы':'Не опубликованы',
    'review-panel':pub.ranking?.length?(pub.ranking.length+' команд в рейтинге'):'Пока пусто'
  };
  for(const [id,label] of Object.entries(badges)){
    const el=$('state-'+id);
    if(el)el.textContent=label;
  }
  if(!guideOpened){
    const next=teamTotal===0?'seating-panel':!teamsDone?'teams-panel':
      !phases.includes('blue')||!finalStacksReady?'scores-panel':
      (pub.revealed_slots||[]).length<3?'secrets-panel':
      !pub.votes_published?'votes-panel':
      !phases.includes('red')?'scores-panel':'control-panel';
    const module=$('module-'+next);
    if(module)module.open=true;
    guideOpened=true;
  }
}
function renderFinalDirector(){
  const p=state.published||{};
  const show=p.final_show;
  const vote=p.vote_show;
  const votesReady=p.votes_published && (!vote || vote.step>=((vote.entries?.length||state.team_count||0)+1));
  const ranking=p.ranking||[];
  const redFinished=(p.published_phases||[]).includes('red');
  const finishOrder=p.blue_policy?.mode==='final_table'&&redFinished;
  const tied=!finishOrder&&ranking.length>1&&ranking[0].total===ranking[1].total;
  const decisionRequired=tied&&!p.winner_decision;
  const ready=votesReady && redFinished && ranking.length>=3 && (!decisionRequired||!!show);
  const step=show?.step??0;
  $('final-show-start').disabled=!ready;
  $('final-show-start').textContent=show?'↻ Начать финал сначала':'▶ Начать FINAL SHOW';
  $('final-show-back').disabled=!show||step===0;
  $('final-show-next').disabled=!show||step>=5;
  $('final-show-next').textContent=step===4?'Показать чемпиона →':'Далее →';
  $('final-show-progress').textContent=show?
    'Кадр '+step+' / 5'+(step===5?' · шоу завершено':' · раскрытие финала'):
    !votesReady?'Сначала заверши голосование':
    !redFinished?'Сначала заверши RED и внеси итоговые места':
    decisionRequired?'НИЧЬЯ: выбери победителя в блоке протокола':
    !ready?'Ожидаем полный рейтинг':'Можно начинать';
}
function renderVoteDirector(){
  const pub=state.published||{};
  const show=pub.vote_show;
  const count=state.team_count||0;
  const complete=state.votes?.length===count&&count>0;
  const secretsDone=pub.secret_show?pub.secret_show.step===4:(pub.revealed_slots?.length||0)===3;
  const ready=complete&&secretsDone&&!pub.votes_published;
  const current=show?.step??0;
  const max=count+1;
  $('publish-votes').disabled=!ready;
  $('publish-votes').textContent=pub.votes_published?
    '✓ Голоса уже зафиксированы':'♠ Зафиксировать голоса и начать шоу';
  $('vote-show-start').disabled=!show||['final','winner'].includes(pub.scene);
  $('vote-show-back').disabled=!show||current===0||['final','winner'].includes(pub.scene);
  $('vote-show-next').disabled=!show||current>=max||['final','winner'].includes(pub.scene);
  $('vote-show-next').textContent=current===count?'Показать итог →':'Далее →';
  $('vote-show-progress').textContent=show?
    'Голос '+Math.min(current,count)+' / '+count+
    (current===max?' · итог раскрыт':' · показ частичных результатов'):
    !secretsDone?'Сначала заверши SECRET JACK SHOW':
    !complete?'Заполни и сохрани голоса всех команд':'Можно опубликовать голоса';
}
function renderSecretDirector(){
  const pub=state.published||{};
  const show=pub.secret_show;
  const revealed=pub.revealed_slots?.length||0;
  const red=pub.red_show;
  const physicalStacks=pub.blue_policy?.mode==='final_table'&&pub.blue_policy?.revealed;
  const redFinished=physicalStacks||((pub.published_phases||[]).includes('red') &&
    (!red||red.step>=((red.ranking?.length||state.team_count||0)+1)));
  const configured=state.secrets?.length===3;
  const ready=redFinished&&configured&&!pub.votes_published;
  const current=show?.step??0;
  $('secret-show-start').disabled=!ready;
  $('secret-show-start').textContent=show?'↻ Начать SECRET JACK сначала':'▶ Начать SECRET JACK SHOW';
  $('secret-show-back').disabled=!show||current===0||!!pub.votes_published;
  $('secret-show-next').disabled=!show||!!pub.votes_published||
    !(current<revealed||(revealed===3&&current===3));
  $('secret-show-next').textContent=revealed===3&&current===3?'Показать итоги →':'Далее →';
  $('reveal-next').disabled=!show||!ready||current!==revealed||revealed>=3;
  $('reveal-next').textContent=revealed<3?'♠ Раскрыть Jack №'+(revealed+1):'Все три Валета раскрыты';
  $('secret-show-progress').textContent=!redFinished?'Сначала объяви стеки финального стола (либо заверши старый RED)'
    :!configured?'Назначь все 3 роли'
    :pub.votes_published?'Голоса уже опубликованы'
    :!show?'Можно начать шоу'
    :'Шаг '+current+' / 4 · раскрыто '+revealed+' / 3'+(current===4?' · готово к голосованию':'');
  $('publish-votes').disabled=!!show&&current<4;
}
function renderRedDirector(){
  const phases=state.published?.published_phases||[];
  const show=state.published?.red_show;
  const completed=phases.includes('red');
  const hasBonuses=state.published?.blue_policy?.mode==='final_table'?false:
    ((state.published?.revealed_slots||[]).length>0 || state.published?.votes_published);
  const current=show?.step??0;
  const max=(show?.ranking?.length??state.team_count??0)+1;
  $('red-show-start').disabled=!completed||hasBonuses;
  $('red-show-start').textContent=show?'↻ Начать RED сначала':'▶ Запустить шоу RED';
  $('red-show-back').disabled=!show||current===0||hasBonuses;
  $('red-show-next').disabled=!show||current>=max||hasBonuses;
  $('red-show-progress').textContent=show
    ?'Шаг '+current+' из '+max+(current>=max?' · RED завершён':' · раскрываем места')
    :hasBonuses?'Бонусы уже раскрыты':completed?'RED опубликован · можешь начать шоу':
     state.published?.blue_policy?.mode==='final_table'?
     'Сначала объяви стеки, раскрой Secret Jack и голоса, затем занеси места RED':'Сначала опубликуй RED';
}
function renderBlueDirector(){
  const phases=state.published?.published_phases||[];
  const show=state.published?.blue_show;
  const ready=phases.includes('blue')&&!phases.includes('red');
  const current=show?.step??0;
  const max=(show?.ranking?.length??state.team_count??0)+1;
  $('blue-show-start').disabled=!ready;
  $('blue-show-start').textContent=show?'↻ Начать BLUE сначала':'▶ Запустить шоу BLUE';
  $('blue-show-back').disabled=!show||current===0||phases.includes('red');
  $('blue-show-next').disabled=!show||current>=max||phases.includes('red');
  $('blue-show-progress').textContent=show
    ?'Шаг '+current+' из '+max+(current>=max?' · BLUE завершён':' · раскрываем места')
    :phases.includes('red')?'RED уже опубликован'
    :phases.includes('blue')?'BLUE опубликован · можешь начать шоу':'Сначала опубликуй BLUE';
}
function renderGreenDirector(){
  const active=(state.published?.published_phases||[]).includes('green');
  const blue=(state.published?.published_phases||[]).includes('blue');
  const show=state.published?.green_show;
  const current=show?.step??0;
  // GREEN: intro (0), positions N..1 (1..N), final list (N+1).
  const max=(show?.ranking?.length??state.team_count??0)+1;
  $('green-show-start').disabled=!active||blue;
  $('green-show-start').textContent=show?'↻ Начать GREEN сначала':'▶ Запустить шоу GREEN';
  $('green-show-back').disabled=!show||current===0;
  $('green-show-next').disabled=!show||current>=max;
  $('green-show-progress').textContent=show
    ?'Шаг '+current+' из '+max+(current>=max?' · GREEN завершён':' · раскрой следующую позицию')
    :active?'GREEN опубликован · можешь запустить шоу':'Сначала опубликуй GREEN';
}
let csrf='';
function toast(message,bad=false){let t=$('toast');t.textContent=message;t.className=bad?'error':'';t.style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.style.display='none',6000)}
async function api(path,method='GET',data=null,isFile=false){const opts={method,credentials:'same-origin',headers:{}};if(method!=='GET')opts.headers['X-CSRF-Token']=csrf;if(data!==null){if(isFile)opts.body=data;else{opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(data)}}const r=await fetch(path,opts);let out;try{out=await r.json()}catch{out={detail:await r.text()}}if(!r.ok)throw new Error(typeof out.detail==='string'?out.detail:JSON.stringify(out.detail||out));return out}
async function refresh(){try{state=await api('/sochi/api/admin/state');csrf=state.csrf;$('login').classList.add('hidden');$('workspace').classList.remove('hidden');$('logout').classList.remove('hidden');render();document.dispatchEvent(new Event('sochi-admin-refreshed'))}catch(e){if(e.message.includes('вход')){$('login').classList.remove('hidden');$('workspace').classList.add('hidden')}else toast(e.message,true)}}
async function change(path,obj){try{const res=await api(path,'POST',obj);toast('Сохранено'+(res.version?' · эфир v'+res.version:''));await refresh();return true}catch(e){toast(e.message,true);return false}}
function optionTeams(selected=null,exclude=null){return '<option value="">— Выберите —</option>'+state.teams.filter(t=>t.team_id!==exclude).map(t=>`<option value="${t.team_id}" ${t.team_id===selected?'selected':''}>${esc(t.display_name)} (#${t.team_id})</option>`).join('')}
function playerOptions(teamId,selected){const seats=state.seats.filter(s=>s.team_id===teamId&&s.player_id);return '<option value="">Капитан не выбран</option>'+seats.map(s=>`<option value="${s.player_id}" ${selected===s.player_id?'selected':''}>${esc(s.player_name)} · стол ${s.table_no}</option>`).join('')}
function render(){let pub=state.published;$('status').textContent=`Команд: ${state.team_count||'—'} · Эфир: ${pub.scene.toUpperCase()} · версия ${state.publication_version} · Обнародовано: ${(pub.published_phases||[]).join(', ')||'нет'}`;$('live-scene').textContent=pub.scene.toUpperCase();$('teamcount').textContent=state.team_count?`${state.team_count} команд · ${state.team_count===10?3:4} стола`:'Нет рассадки';if(state.team_count)$('count').value=String(state.team_count);
const sceneLabels=[['intro','Заставка'],['teams','Показать команды'],['green','Показать GREEN'],['blue','Показать BLUE'],['captains','Представить капитанов'],['red','Показать RED'],['secrets','Secret Jacks']];$('scene-buttons').innerHTML=sceneLabels.map(([key,label])=>`<button data-scene="${key}" class="${key==='green'||key==='blue'||key==='red'?key:'secondary'}">${label}</button>`).join('');
const counts={};state.seats.forEach(s=>counts[s.table_no]=(counts[s.table_no]||0)+1);$('seats-summary').textContent=state.team_count?Object.entries(counts).map(([t,n])=>`Стол ${t}: ${n} боксов`).join(' · ')+` · Привязаны ${state.seats.filter(s=>s.player_id).length}/${state.team_count*3} игроков.`+(state.team_count>10?' · ВНИМАНИЕ: более 10 капитанов — формат RED решает организатор, автоматической рассадки нет.':''):'Импортируйте файл hi_jack_sochi_seating_v2.json с оригинальными вариантами 10–13.';
$('seats').innerHTML=state.seats.map(s=>`<div class="seat-item"><span>Стол ${s.table_no}, бокс ${s.box_no}</span><input data-seat-name="${esc(s.card_id)}" value="${esc(s.player_name||'')}" placeholder="Имя / ник игрока · команда ${s.team_id}"><button class="secondary" data-save-player="${esc(s.card_id)}">Сохранить</button>${s.player_id?`<input type="file" id="seat-photo-${s.player_id}" accept="image/jpeg,image/png,image/webp"><button class="secondary" data-seat-photo="${s.player_id}">Фото${s.has_photo?' ✓':''}</button>${state.published.visible_player_ids?.includes(s.player_id)?`<button class="secondary" data-refresh-photo="${s.player_id}">Фото в эфир</button>`:''}`:''}</div>`).join('');
const activePlayers=state.seats.filter(x=>x.player_id).sort((a,b)=>
  a.team_id-b.team_id||a.table_no-b.table_no||a.box_no-b.box_no);
const teamStats={};
for(const p of activePlayers){
  const entry=teamStats[p.team_id]||(teamStats[p.team_id]={reentry:0,addon:0});
  entry.reentry+=Number(p.player_reentry_count||0);
  entry.addon+=Number(p.player_addon_count||0);
}
$('player-chips-list').innerHTML=activePlayers.length?
  `<div class="scroll"><table class="player-entry-table"><thead><tr><th>Команда / игрок</th><th>Re-entry</th><th>Add-on</th></tr></thead><tbody>${activePlayers.map(p=>{
    const team=state.teams.find(t=>t.team_id===p.team_id);
    const control=kind=>{
      const count=kind==='reentry'?p.player_reentry_count:p.player_addon_count;
      const disabled=(state.published?.published_phases||[]).includes(kind==='reentry'?'green':'blue');
      return `<div class="player-counter"><button type="button" class="secondary" data-pc-action="minus" data-pc-kind="${kind}" data-pc-player="${p.player_id}" ${disabled?'disabled':''}>−</button><input type="number" min="0" max="1000" step="1" id="pc-${p.player_id}-${kind}" value="${Number(count||0)}" ${disabled?'disabled':''}><button type="button" class="secondary" data-pc-action="plus" data-pc-kind="${kind}" data-pc-player="${p.player_id}" ${disabled?'disabled':''}>+</button><button type="button" data-pc-action="save" data-pc-kind="${kind}" data-pc-player="${p.player_id}" ${disabled?'disabled':''}>✓</button></div>`;
    };
    return `<tr><td><strong>${esc(team?.display_name||'Команда '+p.team_id)}</strong><small class="player-place">№${p.team_id} · ${esc(p.player_name)} · стол ${p.table_no}, бокс ${p.box_no}</small></td><td>${control('reentry')}</td><td>${control('addon')}</td></tr>`;
  }).join('')}</tbody></table></div>`:
  '<p class="muted">В рассадке пока нет привязанных игроков.</p>';
$('player-team-summary').innerHTML=state.teams.map(t=>{
  const tracked=teamStats[t.team_id]||{reentry:0,addon:0};
  const total=state.stages[t.team_id]||{};
  return `<span class="player-total">${esc(t.display_name)} · re-entry <b>${total.reentry_count??tracked.reentry}</b> (по игрокам ${tracked.reentry}) · add-on <b>${total.addon_count??tracked.addon}</b> (по игрокам ${tracked.addon})</span>`;
}).join('');
$('teams').innerHTML=state.teams.map(t=>`<div class="team-entry"><span>${t.team_id}</span><small>${esc(t.original_name)}</small><input id="name-${t.team_id}" value="${esc(t.display_name)}" maxlength="45"><select id="capt-${t.team_id}">${playerOptions(t.team_id,t.captain_player_id)}</select><div class="photo-control"><button class="secondary" data-save-name="${t.team_id}">Имя</button><button class="secondary" data-publish-name="${t.team_id}">В эфир</button><button class="secondary" data-save-capt="${t.team_id}">Капитан</button><input type="file" id="photo-${t.team_id}" accept="image/jpeg,image/png,image/webp"><button class="secondary" data-save-photo="${t.team_id}">Фото</button></div></div>`).join('');
const rates=state.chip_settings||{};
$('chips-rates-summary').textContent='Вход: '+(rates.entry==null?'⚠ НЕ НАСТРОЕН · укажи 50 000 перед GREEN':fmt(rates.entry)+' × 3 участника')+' · Re-entry: '+(rates.reentry==null?'не задано':fmt(rates.reentry)+' за 1 шт.')+' · Add-on: '+(rates.addon==null?'не задано':fmt(rates.addon)+' за 1 шт.');
$('stages').querySelector('tbody').innerHTML=state.teams.map(t=>{
  const r=state.stages[t.team_id]||{};
  const keys=['green_stack','reentry_count','blue_stack','addon_count','survivors','red_place'];
  return `<tr><th>${esc(t.display_name)}</th>${keys.map(k=>{
    const kind=k==='reentry_count'?'reentry':k==='addon_count'?'addon':null;
    const tracked=kind?(teamStats[t.team_id]?.[kind]||0):0;
    const derived=kind?(rates[kind]==null?'Норматив не задан':(r[k]!=null?fmt(r[k]*rates[kind])+' фишек':'— фишек'))+
       ' · по игрокам: '+tracked:'';
    return `<td><input type="number" min="${k==='red_place'?1:0}" ${k==='survivors'?'max="3"':kind?'max="1000"':''} ${kind?'data-chip-count="'+kind+'"':''} id="s-${t.team_id}-${k}" value="${r[k]??''}" placeholder="—">${kind?'<small class="chips-derived">'+esc(derived)+'</small>':''}</td>`;
  }).join('')}<td><button data-save-stage="${t.team_id}" class="secondary">✓</button></td></tr>`;
}).join('');
const players=state.seats.filter(s=>s.player_id);$('secret-form').innerHTML=[1,2,3].map(slot=>{let sec=state.secrets.find(x=>x.slot===slot),locked=pub.revealed_slots.includes(slot);return `<div class="secret-item"><strong>#${slot}</strong><select id="secret-player-${slot}"><option value="">Не назначен</option>${players.map(s=>`<option value="${s.player_id}" ${s.player_id===sec?.player_id?'selected':''}>${esc(s.player_name)} · №${s.team_id} · стол ${s.table_no}</option>`).join('')}</select><select id="secret-killer-${slot}">${optionTeams(sec?.knockout_team_id)}</select><select id="secret-knockout-player-${slot}"><option value="">Кто выбил?</option>${players.map(s=>`<option value="${s.player_id}" ${s.player_id===sec?.knockout_player_id?'selected':''}>${esc(s.player_name)} · №${s.team_id}</option>`).join('')}</select><div><label><input type="checkbox" id="secret-confirm-${slot}" ${sec?.confirmed?'checked':''}>Выбит</label><button data-save-secret="${slot}" class="secondary">Сохранить</button></div></div>`}).join('');
$('vote-mode').value=state.vote_mode;$('vote-mode').disabled=pub.votes_published;$('vote-form').innerHTML=state.teams.map(t=>{let vote=state.votes.find(v=>v.voter_team_id===t.team_id);return `<div class="vote-item"><strong>№${t.team_id}</strong><span>${esc(t.display_name)}</span><select id="vote-${t.team_id}" ${pub.votes_published?'disabled':''}>${optionTeams(vote?.target_team_id,t.team_id)}</select><button data-save-vote="${t.team_id}" class="secondary" ${pub.votes_published?'disabled':''}>✓</button></div>`}).join('');
let rk=pub.ranking;const finishedByRed=pub.blue_policy?.mode==='final_table'&&(pub.published_phases||[]).includes('red');$('ranking-preview').innerHTML=rk.length?(finishedByRed?'<p><strong>МЕСТА ОПРЕДЕЛЯЕТ ВЫБЫВАНИЕ КАПИТАНОВ RED.</strong> Очки только справочно.</p>':'')+`<table class="ranking-mini"><tr><th>№</th><th>Команда</th><th>GREEN</th><th>BLUE</th><th>RED</th><th>Secret</th><th>Голоса</th><th>Итого</th></tr>${rk.map(r=>`<tr><td>${r.place}</td><td>${esc(r.name)}${r.tied?' · НИЧЬЯ':''}</td>${['green','blue','red','secret','votes','total'].map(k=>`<td>${fmt(r[k])}</td>`).join('')}</tr>`).join('')}</table>`:'<p class="muted">Рейтинг появится после публикации команд.</p>';
const ties=finishedByRed?[]:rk.length>1?rk.filter(r=>r.total===rk[0].total):[];$('tie-resolution').innerHTML=ties.length>1?`<span class="note">НИЧЬЯ НА ПЕРВОМ МЕСТЕ · решение организатора:</span><select id="tie-winner">${ties.map(t=>`<option value="${t.team_id}" ${pub.winner_decision===t.team_id?'selected':''}>${esc(t.name)}</option>`).join('')}</select><button id="save-tie" class="gold">Зафиксировать решение</button>`:'';
$('audit').innerHTML=state.audit.map(x=>`<div class="audit-entry">${esc(x.created_at)} · ${esc(x.action)} · ${esc(x.data).slice(0,300)}</div>`).join('');updateWorkflow();renderGreenDirector();renderBlueDirector();renderRedDirector();renderSecretDirector();renderVoteDirector();renderFinalDirector();}
$('login-form').onsubmit=async e=>{e.preventDefault();try{await api('/sochi/api/admin/login','POST',{password:$('password').value});$('password').value='';await refresh()}catch(err){toast(err.message,true)}};
$('logout').onclick=async()=>{await change('/sochi/api/admin/logout',{});location.reload()};
$('import').onclick=async()=>{const file=$('json-file').files[0];if(!file)return toast('Выберите файл JSON',true);let obj;try{obj=JSON.parse(await file.text())}catch{return toast('Неверный JSON',true)}let n=Number($('count').value);let assigned=state.seats.some(s=>s.player_id);let confirm_replace_cards=false;if(assigned){confirm_replace_cards=confirm(`ВНИМАНИЕ: у участников уже есть карточки. Смена схемы требует ФИЗИЧЕСКОЙ ЗАМЕНЫ карточек. Подтвердить?`);if(!confirm_replace_cards)return}await change('/sochi/api/admin/seating',{document:obj,team_count:n,confirm_replace_cards})};
$('publish-teams').onclick=()=>publish({action:'teams'},'Опубликовать названия всех команд?');$('publish-captains').onclick=()=>{
  if(!state.team_count)return toast('Сначала импортируй рассадку',true);
  const captain_assignments=state.teams.map(t=>{
    const value=$('capt-'+t.team_id).value;
    return {team_id:t.team_id,captain_player_id:value?Number(value):null};
  });
  const selected=captain_assignments.filter(x=>x.captain_player_id!==null).length;
  if(!selected)return toast('Сначала выбери хотя бы одного капитана',true);
  return publish({action:'captains',captain_assignments},
    'СОХРАНИТЬ и ОПУБЛИКОВАТЬ '+selected+' капитанов из '+state.team_count+' команд? '+(selected<state.team_count?'Не выбранные капитаны останутся пустыми.':''));
};$('publish-votes').onclick=()=>publish(
  {action:'votes',show_mode:'cinematic'},
  'Зафиксировать все голоса и открыть только ЗАСТАВКУ голосования? Кнопка «Далее» будет раскрывать голоса по одному.'
);
$('vote-show-start').onclick=()=>publish({action:'vote-show-start'},
  'Повторить шоу голосования с заставки? Баллы повторно не начисляются.');
$('vote-show-back').onclick=async()=>{
  const show=state.published?.vote_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'vote-show-step',step:show.step-1});
};
$('vote-show-next').onclick=async()=>{
  const show=state.published?.vote_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'vote-show-step',step:show.step+1});
};
$('final-show-start').onclick=()=>publish({action:'final-show-start'},
  'Начать или повторить FINAL SHOW на публичном проекторе? Сначала появится только заставка без призовых мест.');
$('final-show-back').onclick=async()=>{
  const show=state.published?.final_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'final-show-step',step:show.step-1});
};
$('final-show-next').onclick=async()=>{
  const show=state.published?.final_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'final-show-step',step:show.step+1});
};$('vote-mode').onchange=e=>change('/sochi/api/admin/vote-mode',{mode:e.target.value});$('reveal-next').onclick=()=>{
  const slot=(state.published.revealed_slots?.length||0)+1;
  if(!state.published.secret_show)return toast('Сначала запусти SECRET JACK SHOW',true);
  if(slot>3)return toast('Все три Валета раскрыты');
  const bonus=state.published?.blue_policy?.mode==='final_table'?'5 000 фишек':'10 000 очков';
  publish({action:'reveal',slot},`ВПЕРВЫЕ раскрыть SECRET JACK №${slot} на проекторе? При подтверждённом выбивании начислится +${bonus} один раз.`);
};
$('secret-show-start').onclick=()=>publish({action:'secret-show-start'},'Запустить или повторить SECRET JACK SHOW? Это не начисляет дополнительные очки.');
$('secret-show-back').onclick=async()=>{
  const show=state.published?.secret_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'secret-show-step',step:show.step-1});
};
$('secret-show-next').onclick=async()=>{
  const show=state.published?.secret_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'secret-show-step',step:show.step+1});
};
$('tie-resolution').onclick=async e=>{if(e.target.id==='save-tie')await publish({action:'winner-decision',team_id:Number($('tie-winner').value)},'Подтвердить победителя по решению организатора при ничьей?')};$('close-preview').onclick=()=>$('preview-modal').close();$('preview-screen').onclick=()=>{previewText(`<pre style="white-space:pre-wrap">${esc(JSON.stringify(state.published,null,2))}</pre>`)};function previewText(html){$('preview-body').innerHTML=html;$('preview-modal').showModal()};
async function publish(body,message){if(!confirm(message))return;await change('/sochi/api/admin/publish',body)}
function valsTeam(team){
  let obj={team_id:team};
  for(const k of ['green_stack','reentry_count','blue_stack','addon_count','survivors','red_place']){
    const value=$(`s-${team}-${k}`).value;
    if(value!=='')obj[k]=Number(value);
  }
  return obj;
}
async function bulkStage(stage){
  if(!state.team_count)return toast('Сначала импортируй рассадку',true);
  if(!Object.keys(state.published.teams||{}).length)return toast('Сначала опубликуй названия команд',true);
  const rates=state.chip_settings||{};
  if(stage==='green'&&rates.entry==null)return toast('Сначала сохрани стоимость ВХОДА одного игрока (50 000 по правилам)',true);
  if(stage==='green'&&rates.reentry==null)return toast('Сначала укажи норматив re-entry в настройках фишек',true);
  if(stage==='blue'){
    if(!(state.published.published_phases||[]).includes('green'))return toast('Сначала опубликуй GREEN',true);
    if(rates.addon==null)return toast('Сначала укажи норматив add-on в настройках фишек',true);
  }
  const keys={green:['green_stack','reentry_count'],blue:['blue_stack','addon_count','survivors'],red:['red_place']}[stage];
  const rows=[];
  for(const t of state.teams){
    const inputs=valsTeam(t.team_id);
    if(keys.some(k=>inputs[k]===undefined))return toast(`Команда ${t.team_id}: заполните поля ${stage.toUpperCase()}`,true);
    if(keys.some(k=>!Number.isSafeInteger(inputs[k])||inputs[k]<0))return toast(`Команда ${t.team_id}: нужны неотрицательные целые числа`,true);
    rows.push({team_id:t.team_id,...Object.fromEntries(keys.map(k=>[k,inputs[k]]))});
  }
  if(stage==='red'){
    const places=rows.map(x=>x.red_place).sort((a,b)=>a-b);
    if(!places.every((p,i)=>p===i+1))return toast('RED: каждому месту от 1 до N — ровно одна команда',true);
  }
  const preview=state.teams.map(t=>{
    const r=valsTeam(t.team_id);
    let score,detail;
    if(stage==='green'){
      const chips=r.reentry_count*rates.reentry;
      const entry=3*(rates.entry||0);
      score=r.green_stack-chips-entry;
      detail=`стек ${fmt(r.green_stack)} − 3 × ${fmt(rates.entry||0)} вход − ${r.reentry_count} × ${fmt(rates.reentry)} re-entry`;
    }else if(stage==='blue'){
      const chips=r.addon_count*rates.addon;
      const prev=state.stages[t.team_id]||{};
      const reentry=(prev.reentry_count||0)*(rates.reentry||0);
      const entry=3*(rates.entry||0);
      score=r.blue_stack-entry-reentry-chips;
      detail=`стек на конец BLUE ${fmt(r.blue_stack)} − входы ${fmt(entry)} − re-entry ${fmt(reentry)} − add-on ${fmt(chips)}; +${fmt(5000*r.survivors)} бонусных ОЧКОВ за выживших (отдельно, на место BLUE не влияет)`;
    }else{
      score=130000-10000*(r.red_place-1);
      detail=state.published?.blue_policy?.mode==='final_table'?`финиш RED №${r.red_place} → ИТОГОВОЕ МЕСТО КОМАНДЫ №${r.red_place}`:`место №${r.red_place}`;
    }
    return `№${t.team_id} · ${t.display_name}: ${stage==='red'&&state.published?.blue_policy?.mode==='final_table'?'ИТОГОВОЕ МЕСТО #'+r.red_place:fmt(score)+' '+(stage==='red'?'очков':'чистых фишек')} [${detail}]`;
  }).join('\n');
  previewText(`<p>${stage==='blue'?'Проверь ОКОНЧАТЕЛЬНЫЕ чистые фишки BLUE. Места считаются только по фишкам; бонус выживших +5 000 за человека начисляется к очкам отдельно. После раскрытия мест утверди и объяви пропорциональные стеки капитанам в блоке BLUE → ФИНАЛЬНЫЙ СТОЛ.':stage==='green'?'Проверь ПРОМЕЖУТОЧНЫЕ чистые фишки GREEN. Этот результат не суммируется повторно с итогом BLUE. Далее раскрывай места в GREEN SHOW.':stage==='red'?'Проверь места капитанов RED (1 = победитель, N = первый вылетевший). Это итоговые места команд независимо от очков. После публикации места раскрываются по кнопке «Далее».':'Проверь расчёты. После подтверждения данные этапа будут опубликованы на проекторе.'}</p><pre style="white-space:pre-wrap">${esc(preview)}</pre><button id="confirm-pub-stage" class="gold">Сохранить и опубликовать ${stage.toUpperCase()}</button>`);
  $('confirm-pub-stage').onclick=async()=>{
    try{
      await api('/sochi/api/admin/stages/bulk','POST',{phase:stage,teams:rows});
      await api('/sochi/api/admin/publish','POST',{action:stage,...(['green','blue','red'].includes(stage)?{show_mode:'cinematic'}:{})});
      $('preview-modal').close();
      toast(`Этап ${stage.toUpperCase()} опубликован`);
      await refresh();
    }catch(e){toast(e.message,true)}
  };
}
function openChipSettings(){
  const settings=state.chip_settings||{};
  const phases=state.published.published_phases||[];
  $('chips-per-entry').value=settings.entry??50000;
  $('chips-per-entry').disabled=phases.includes('green');
  $('chips-per-reentry').value=settings.reentry??'';
  $('chips-per-addon').value=settings.addon??'';
  $('chips-per-reentry').disabled=phases.includes('green');
  $('chips-per-addon').disabled=phases.includes('blue');
  $('chips-settings-modal').showModal();
}
$('green-show-start').onclick=()=>publish({action:'green-show-start'},'Запустить GREEN SHOW на публичном проекторе? Рейтинг будет раскрываться по шагам.');
$('green-show-next').onclick=async()=>{
  const show=state.published?.green_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'green-show-step',step:show.step+1});
};
$('green-show-back').onclick=async()=>{
  const show=state.published?.green_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'green-show-step',step:show.step-1});
};
$('blue-show-start').onclick=()=>publish({action:'blue-show-start'},'Запустить или повторить BLUE SHOW на публичном проекторе?');
$('blue-show-next').onclick=async()=>{
  const show=state.published?.blue_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'blue-show-step',step:show.step+1});
};
$('blue-show-back').onclick=async()=>{
  const show=state.published?.blue_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'blue-show-step',step:show.step-1});
};
$('red-show-start').onclick=()=>publish({action:'red-show-start'},'Запустить или повторить RED SHOW на публичном проекторе?');
$('red-show-next').onclick=async()=>{
  const show=state.published?.red_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'red-show-step',step:show.step+1});
};
$('red-show-back').onclick=async()=>{
  const show=state.published?.red_show;
  if(!show)return;
  await change('/sochi/api/admin/publish',{action:'red-show-step',step:show.step-1});
};
$('open-chips-settings').onclick=openChipSettings;
$('close-chips-settings').onclick=()=>$('chips-settings-modal').close();
$('chips-settings-form').onsubmit=async event=>{
  event.preventDefault();
  const body={};
  for(const [kind,id] of [['entry','chips-per-entry'],['reentry','chips-per-reentry'],['addon','chips-per-addon']]){
    const field=$(id);
    if(field.disabled||field.value==='')continue;
    const n=Number(field.value);
    if(!Number.isSafeInteger(n)||n<(kind==='entry'?0:1)||n>1000000000)return toast('Недопустимое число фишек',true);
    body[kind]=n;
  }
  if(!Object.keys(body).length)return toast('Укажи хотя бы один норматив фишек',true);
  try{
    await api('/sochi/api/admin/chips-settings','POST',body);
    $('chips-settings-modal').close();
    toast('Нормативы фишек сохранены');
    await refresh();
  }catch(e){toast(e.message,true)}
};
document.addEventListener('input',event=>{
  const field=event.target.closest('[data-chip-count]');
  if(!field||!state)return;
  const kind=field.dataset.chipCount;
  const rate=state.chip_settings?.[kind];
  const detail=field.parentElement.querySelector('.chips-derived');
  if(!detail)return;
  if(rate==null){detail.textContent='Укажи норматив';return}
  if(field.value===''){detail.textContent='— фишек';return}
  const count=Number(field.value);
  detail.textContent=Number.isSafeInteger(count)&&count>=0&&count<=1000
    ?fmt(count*rate)+' фишек':'Недопустимое количество';
});

document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;const d=b.dataset;
if(d.pcAction){
  const player_id=Number(d.pcPlayer),kind=d.pcKind;
  const input=$('pc-'+player_id+'-'+kind);
  if(!input)return;
  const request={player_id,kind};
  if(d.pcAction==='plus')request.delta=1;
  else if(d.pcAction==='minus')request.delta=-1;
  else {
    if(input.value.trim()===''||!Number.isSafeInteger(Number(input.value))||
       Number(input.value)<0||Number(input.value)>1000)
      return toast('Введи целое количество от 0 до 1000',true);
    request.count=Number(input.value);
  }
  await change('/sochi/api/admin/player-chips',request);
  return;
}
if(d.scene){await publish({action:'scene',scene:d.scene},`Переключить проектор: ${d.scene.toUpperCase()}?`)}if(d.stage){bulkStage(d.stage)}if(d.savePlayer){const s=state.seats.find(x=>x.card_id===d.savePlayer);const name=document.querySelector(`[data-seat-name="${CSS.escape(d.savePlayer)}"]`).value;await change('/sochi/api/admin/player',{card_id:d.savePlayer,name,confirm_rebind:!!s.player_id})}if(d.saveName){let id=Number(d.saveName);await change('/sochi/api/admin/team',{team_id:id,display_name:$(`name-${id}`).value})}if(d.publishName){await publish({action:'name',team_id:Number(d.publishName)},'Опубликовать новое название команды?')}if(d.saveCapt){let id=Number(d.saveCapt),value=$(`capt-${id}`).value;await change('/sochi/api/admin/team',{team_id:id,captain_player_id:value?Number(value):null})}if(d.savePhoto){let id=Number(d.savePhoto),capt=$(`capt-${id}`).value,file=$(`photo-${id}`).files[0];if(!capt||!file)return toast('Выберите капитана и фото',true);let fd=new FormData();fd.append('file',file);try{await api('/sochi/api/admin/photo/'+capt,'POST',fd,true);toast('Фото сохранено в закрытом хранилище. Опубликуйте капитанов для эфира.');await refresh()}catch(e){toast(e.message,true)}}if(d.saveStage){let obj=valsTeam(Number(d.saveStage));await change('/sochi/api/admin/stage',obj)}if(d.saveSecret){let slot=Number(d.saveSecret),pid=Number($(`secret-player-${slot}`).value),killer=$(`secret-killer-${slot}`).value,killerPlayer=$(`secret-knockout-player-${slot}`).value,confirmed=$(`secret-confirm-${slot}`).checked;if(!pid)return toast('Сначала привяжите Secret Jack к участнику',true);const data={slot,player_id:pid,knockout_team_id:killer?Number(killer):null,knockout_player_id:killerPlayer?Number(killerPlayer):null,confirmed};const shown=state.published.revealed_slots.includes(slot);if(shown){
  toast('Раскрытого Secret Jack исправляй в 🔐 Защищённом редакторе с PIN');
  $('protected-kind').value='secret';
  $('protected-kind').dispatchEvent(new Event('change'));
  $('protected-slot').value=String(slot);
  $('protected-slot').dispatchEvent(new Event('change',{bubbles:true}));
  $('protected-editor-panel').scrollIntoView({behavior:'smooth',block:'start'});
  return;
}await change('/sochi/api/admin/secret',data)}if(d.seatPhoto){let pid=Number(d.seatPhoto),file=$(`seat-photo-${pid}`).files[0];if(!file)return toast('Выберите фото',true);let fd=new FormData();fd.append('file',file);try{await api('/sochi/api/admin/photo/'+pid,'POST',fd,true);toast('Фото в закрытом хранилище');await refresh()}catch(e){toast(e.message,true)}}if(d.refreshPhoto){await publish({action:'refresh-photo',player_id:Number(d.refreshPhoto)},'Опубликовать обновлённую фотографию игрока?')}if(d.saveVote){let id=Number(d.saveVote),target=Number($(`vote-${id}`).value);if(!target)return toast('Выберите команду',true);await change('/sochi/api/admin/vote',{voter_team_id:id,target_team_id:target})}});
installModuleLayout();
refresh();
