'use strict';
/* PIN-verified, version-bound correction workflow.
 * No effect on the projector until the operator sees a before/after preview.
 * Uses the normal admin CSRF/session, does not keep the PIN after submission.
 */
(()=>{
const el=id=>document.getElementById(id);
const escapeText=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let pending=null;
function options(rows,valueKey,labelKey,selected){
 return rows.map(row=>`<option value="${escapeText(row[valueKey])}" ${String(selected)===String(row[valueKey])?'selected':''}>${escapeText(typeof labelKey==='function'?labelKey(row):row[labelKey])}</option>`).join('');
}
const teams=()=>state?.teams||[];
const seats=()=>state?.seats||[];
const assigned=()=>seats().filter(s=>s.player_id);
const tselect=(id,label)=>`<label>${label}<select id="${id}">${options(teams(),'team_id',r=>'#'+r.team_id+' · '+r.display_name)}</select></label>`;
const pselect=(id,label,onlyTeam=null)=>`<label>${label}<select id="${id}"><option value="">— не выбрано —</option>${options(assigned().filter(p=>onlyTeam===null||p.team_id===onlyTeam),'player_id',r=>r.player_name+' / команда '+r.team_id+' / '+r.card_id)}</select></label>`;
const select=(id,label,choices)=>`<label>${label}<select id="${id}">${choices.map(([v,name])=>`<option value="${escapeText(v)}">${escapeText(name)}</option>`).join('')}</select></label>`;
const textField=(type='text',label='Новое значение',placeholder='')=>`<label>${label}<input id="protected-value" type="${type}" placeholder="${escapeText(placeholder)}" autocomplete="off"></label>`;
const clearField=()=>`<label class="protected-clear"><input id="protected-clear" type="checkbox"> Удалить/очистить значение (может снять этап с публикации)</label>`;
const stageLabels=[['green_stack','GREEN: стек фишек'],['reentry_count','GREEN: количество re-entry'],['blue_stack','BLUE: стек фишек'],['addon_count','BLUE: количество add-on'],['survivors','BLUE: оставшиеся игроки (0–3)'],['red_place','RED: место капитана (автообмен при совпадении)']];
function changeFields(){
 pending=null;
 el('protected-result').innerHTML='';
 el('protected-confirm').classList.add('hidden');
 const kind=el('protected-kind').value;
 let html='';
 if(kind==='stage')html=tselect('protected-team','Команда')+select('protected-field','Показатель',stageLabels)+textField('number','Новое целое число')+clearField();
 else if(kind==='chip_rate')html=select('protected-field','Норматив',[['reentry','Число фишек за re-entry'],['addon','Число фишек за add-on']])+textField('number','Новое значение (больше 0)');
 else if(kind==='team_name')html=tselect('protected-team','Команда')+textField('text','Новое название');
 else if(kind==='captain')html=tselect('protected-team','Команда')+pselect('protected-player','Новый капитан')+clearField();
 else if(kind==='player_name')html=pselect('protected-player','Игрок')+textField('text','Новое имя или никнейм');
 else if(kind==='seat')html=select('protected-card','Карточка рассадки',seats().map(s=>[s.card_id,'Стол '+s.table_no+', бокс '+s.box_no+' · '+s.card_id+' · команда '+s.team_id]))+textField('text','Имя нового игрока (создать и назначить)')+clearField();
 else if(kind==='secret')html=select('protected-slot','Номер Secret Jack',[[1,'Secret Jack №1'],[2,'Secret Jack №2'],[3,'Secret Jack №3']])+pselect('protected-player','Какой игрок — Secret Jack')+tselect('protected-killer-team','Какая команда выбила?')+pselect('protected-killer-player','Кто выбил?')+`<label><input id="protected-confirmed" type="checkbox"> Выбит (начислить бонус +10 000)</label>`+clearField();
 else if(kind==='vote')html=tselect('protected-team','Кто голосовал')+tselect('protected-target','За какую команду')+clearField();
 else if(kind==='vote_mode')html=select('protected-field','Получатель бонуса',[['target','Выбранная команда'],['voter','Голосующая команда']]);
 else if(kind==='winner')html=tselect('protected-team','Победитель, выбранный организатором')+clearField();
 el('protected-fields').innerHTML=html;
 for(const ctrl of el('protected-fields').querySelectorAll('input,select')){
  ctrl.addEventListener('input',()=>{
    pending=null;el('protected-result').innerHTML='';el('protected-confirm').classList.add('hidden');
  });
 }
 // Prefill current known values, so editing one item never silently clears another.
 prefill();
}
function value(id){return el(id)?.value??''}
function prefill(){
 const kind=value('protected-kind');
 const tid=Number(value('protected-team'));
 if(kind==='stage'){
  const field=value('protected-field'),row=state?.stages?.[tid];
  el('protected-value').value=row?.[field]??'';
 }else if(kind==='chip_rate')el('protected-value').value=state?.chip_settings?.[value('protected-field')]??'';
 else if(kind==='team_name')el('protected-value').value=teams().find(t=>t.team_id===tid)?.display_name||'';
 else if(kind==='player_name')el('protected-value').value=assigned().find(s=>s.player_id===Number(value('protected-player')))?.player_name||'';
 else if(kind==='seat')el('protected-value').value='';
 else if(kind==='vote'){
  const previous=state?.votes?.find(v=>v.voter_team_id===tid);
  if(previous)el('protected-target').value=String(previous.target_team_id);
 }else if(kind==='secret'){
  const r=state?.secrets?.find(s=>s.slot===Number(value('protected-slot')));
  if(r){
    el('protected-player').value=String(r.player_id);
    el('protected-confirmed').checked=!!r.confirmed;
    if(r.knockout_team_id)el('protected-killer-team').value=String(r.knockout_team_id);
    if(r.knockout_player_id)el('protected-killer-player').value=String(r.knockout_player_id);
  }
 }else if(kind==='vote_mode')el('protected-field').value=state?.vote_mode||'target';
 else if(kind==='captain'){
  const r=teams().find(t=>t.team_id===tid);
  if(r?.captain_player_id)el('protected-player').value=String(r.captain_player_id);
 }else if(kind==='winner'){
  if(state?.published?.winner_decision)el('protected-team').value=String(state.published.winner_decision);
 }
}
function requestBody(){
 const kind=value('protected-kind'),clear=el('protected-clear')?.checked===true;
 const body={kind,clear,expected_version:state.publication_version};
 if(['stage','team_name','captain','vote','winner'].includes(kind))body.team_id=Number(value('protected-team'));
 if(kind==='stage'){body.field=value('protected-field');const raw=value('protected-value');if(!clear){if(raw===''||!Number.isSafeInteger(Number(raw)))throw Error('Введи корректное целое число');body.value=Number(raw)}}
 if(kind==='chip_rate'){body.field=value('protected-field');const raw=value('protected-value');if(raw===''||!Number.isSafeInteger(Number(raw)))throw Error('Введи целое число');body.value=Number(raw)}
 if(kind==='team_name')body.value=value('protected-value');
 if(kind==='player_name'){body.player_id=Number(value('protected-player'));body.value=value('protected-value')}
 if(kind==='captain'&&!clear)body.value=Number(value('protected-player'));
 if(kind==='seat'){body.card_id=value('protected-card');if(!clear)body.value=value('protected-value')}
 if(kind==='secret'){
   body.slot=Number(value('protected-slot'));
   if(!clear){
     body.player_id=Number(value('protected-player'));
     body.confirmed=el('protected-confirmed').checked;
     body.knockout_team_id=body.confirmed?Number(value('protected-killer-team')):null;
     body.knockout_player_id=body.confirmed?Number(value('protected-killer-player')):null;
   }
 }
 if(kind==='vote'&&!clear)body.value=Number(value('protected-target'));
 if(kind==='vote_mode')body.value=value('protected-field');
 if(kind==='winner'&&!clear)body.value=Number(value('protected-team'));
 return body;
}
function readable(v){if(v===null||v===undefined)return '— (пусто)';
 if(typeof v==='object')return JSON.stringify(v,null,2);
 return String(v);
}
function renderPreview(preview){
 const warning=preview.retracted_phases?.length?
  '<p class="error"><strong>ВНИМАНИЕ:</strong> будут сняты с публикации этапы: '+
  preview.retracted_phases.map(escapeText).join(', ')+'. Нужно будет заново заполнить данные и опубликовать этап.</p>':'';
 const rows=(preview.score_changes||[]).slice(0,22).map(r=>
   `<tr><td>${escapeText(r.name)}</td><td>${r.old_place} → ${r.new_place}</td><td>${r.old_total.toLocaleString('ru-RU')} → ${r.new_total.toLocaleString('ru-RU')}</td></tr>`).join('');
 el('protected-result').innerHTML=`<div class="protected-compare">
    <h3>${escapeText(preview.label)}</h3>
    <div class="protected-compare-grid"><div><b>БЫЛО</b><pre>${escapeText(readable(preview.before))}</pre></div>
      <div><b>БУДЕТ</b><pre>${escapeText(readable(preview.after))}</pre></div></div>
    ${warning}
    <p>Экран: ${escapeText(preview.old_scene)} → ${escapeText(preview.new_scene)}.
      Лидер: ${escapeText(preview.old_leader||'—')} → ${escapeText(preview.new_leader||'—')}.</p>
    ${rows?`<table><thead><tr><th>Команда</th><th>Место</th><th>Очки</th></tr></thead><tbody>${rows}</tbody></table>`:
       '<p class="muted">Места и очки не изменились либо этап ещё не опубликован.</p>'}
  </div>`;
 el('protected-confirm').classList.remove('hidden');
}
el('protected-kind').addEventListener('change',changeFields);
el('protected-fields').addEventListener('change',e=>{
 if(e.target.id==='protected-team'||e.target.id==='protected-field'||e.target.id==='protected-player'||e.target.id==='protected-slot'){
  const kind=value('protected-kind');
  if(['stage','chip_rate','team_name','player_name','captain','vote','secret'].includes(kind))prefill();
 }
});
el('protected-preview').addEventListener('click',async()=>{
 try{
  if(!state)throw Error('Войди в админку');
  const body=requestBody();
  const response=await api('/sochi/api/admin/correction/preview','POST',body);
  pending={...body};
  renderPreview(response.preview);
  el('protected-pin').value='';
  el('protected-phrase').value='';
 }catch(error){pending=null;el('protected-confirm').classList.add('hidden');toast(error.message,true)}
});
el('protected-confirm').addEventListener('submit',async e=>{
 e.preventDefault();
 if(!pending)return toast('Сначала проверь последствия',true);
 const pin=el('protected-pin').value;
 const reason=el('protected-reason').value.trim();
 const confirmText=el('protected-phrase').value.trim();
 el('protected-pin').value='';
 try{
  const result=await api('/sochi/api/admin/correction/apply','POST',{
    ...pending,pin,reason,confirm:confirmText
  });
  pending=null;
  el('protected-confirm').classList.add('hidden');
  toast('Исправление применено · эфир v'+result.version);
  await refresh();
  changeFields();
 }catch(error){toast(error.message,true)}
});
el('protected-history-btn').addEventListener('click',async()=>{
 try{
   const result=await api('/sochi/api/admin/corrections/history');
   const host=el('protected-history');
   host.classList.remove('hidden');
   host.innerHTML=`<h3>Последние исправления</h3>`+(result.history||[]).map(row=>
     `<div class="protected-history-entry"><strong>#${row.id} · ${escapeText(row.created_at)} · ${escapeText(row.field_name)}</strong>
        <p>${escapeText(row.reason)}</p><pre>${escapeText(row.previous_value)} → ${escapeText(row.updated_value)}</pre></div>`).join('');
 }catch(error){toast(error.message,true)}
});
changeFields();
})();
