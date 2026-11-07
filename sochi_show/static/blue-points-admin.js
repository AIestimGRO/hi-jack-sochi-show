'use strict';
/* HI JACK / SOCHI: director for net BLUE chips -> pre-RED tournament points.
   Preview is private. Publishing points is a separate deliberate screen action.
 */
(()=>{
  const $=id=>document.getElementById(id);
  const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=n=>new Intl.NumberFormat('ru-RU').format(n||0);
  let pending=null, lastCount=0, editing=false;
  const teams=()=>state?.teams||[];
  const phase=()=>state?.published||{};
  const blueReady=()=>{
    const p=phase();
    return (p.published_phases||[]).includes('blue')
      &&(!p.blue_show||p.blue_show.step>=p.blue_show.ranking.length+1);
  };
  const rows=()=>{
    const published=phase(),names=new Map(teams().map(t=>[t.team_id,t.display_name]));
    const arr=Object.entries(published.stages||{}).filter(([id,r])=>
      Number.isSafeInteger(r.green)&&Number.isSafeInteger(r.blue)).map(([id,r])=>
        ({id:Number(id),name:names.get(Number(id))||'Команда #'+id,
          chips:r.blue_net_chips??(r.green+r.blue),bonus:r.survivor_bonus||0,
          green:r.green,blue:r.blue}));
    arr.sort((a,b)=>b.chips-a.chips||a.id-b.id);
    arr.forEach((r,i)=>r.place=i&&r.chips===arr[i-1].chips?arr[i-1].place:i+1);
    return arr;
  };
  const defaults=count=>Array.from({length:count},(_,i)=>Math.max(0,130000-i*10000));
  const manualValues=()=>{
    const boxes=[...document.querySelectorAll('#bp-points-table [data-bp-place]')];
    if(!boxes.length)return defaults(state?.team_count||10);
    return boxes.map(x=>{
      const n=x.value.trim()===''?NaN:Number(x.value);
      if(!Number.isSafeInteger(n)||n<0||n>10000000)throw Error('Все очки за места должны быть целыми от 0 до 10 000 000');
      return n;
    });
  };
  function model(){
    const mode=$('bp-mode').value;
    const percent=Number($('bp-percent').value);
    if(mode==='scale'&&(!Number.isSafeInteger(percent)||percent<1||percent>100))throw Error('Коэффициент 1–100%');
    const place_points=mode==='places'?manualValues():[];
    if(place_points.some((x,i)=>i>0&&x>place_points[i-1]))throw Error('Очки должны не возрастать с ухудшением места');
    return {mode,percent:mode==='scale'?percent:100,place_points};
  }
  function points(row,policy){
    if(policy.mode==='chips')return row.chips;
    if(policy.mode==='scale'){
      const abs=Math.floor((Math.abs(row.chips)*policy.percent+50)/100);
      return row.chips<0?-abs:abs;
    }
    return policy.place_points[row.place-1];
  }
  function previewTable(policy){
    const ranked=rows();
    if(!ranked.length)return '<p class="muted">Сначала опубликуй GREEN и BLUE — чистые фишки появятся здесь автоматически.</p>';
    const scores=ranked.map(r=>points(r,policy));
    const gap=Math.max(...scores)-Math.min(...scores);
    const redMaxSwing=(ranked.length-1)*10000;
    return `<div class="bp-summary"><strong>Разрыв между первым и последним:</strong>
      ${fmt(gap)} очков <span>· разница RED между первым и последним местом: ${fmt(redMaxSwing)} очков</span>
      <span>Бонус +5 000 за выжившего считается отдельно и не определяет места BLUE.</span>
      ${gap>redMaxSwing?'<b class="bp-warning">Большой разрыв — RED может не изменить лидера</b>':'<b class="bp-good">Борьба за места после RED сохраняется</b>'}
    </div>
    <table class="bp-table"><thead><tr><th>Место</th><th>Команда</th><th>Чистые фишки BLUE</th><th>Выжившие · бонус</th><th>Очки перед RED</th></tr></thead>
    <tbody>${ranked.map((r,i)=>`<tr class="${i===0?'bp-leading':''}"><td>#${r.place}</td><td>${escapeHTML(r.name)}</td>
      <td>${fmt(r.chips)}</td><td>+${fmt(r.bonus)}</td><td><strong>${fmt(scores[i]+r.bonus)}</strong></td></tr>`).join('')}</tbody></table>`;
  }
  function render(){
    const count=state?.team_count||0, p=phase(),policy=p.blue_policy||null;
    const mode=$('bp-mode').value;
    $('bp-scale-label').classList.toggle('hidden',mode!=='scale');
    const show=mode==='places'&&count>0;
    if(show&&(!editing||lastCount!==count||!$('bp-points-table').querySelector('[data-bp-place]'))){
      const vals=policy?.mode==='places'&&policy.place_points?.length===count
        ?policy.place_points:defaults(count);
      $('bp-points-table').innerHTML=`<div class="bp-manual-grid">${vals.map((v,i)=>
        `<label>${i+1}-е место<input data-bp-place="${i+1}" type="number" min="0" max="10000000" step="1000" value="${v}"></label>`).join('')}</div>`;
      lastCount=count;
    }
    if(!show){$('bp-points-table').innerHTML='';lastCount=0}
    const ready=blueReady();
    $('bp-preview').disabled=!ready;
    const finished=!!(p.published_phases||[]).includes('red');
    $('bp-reveal').disabled=!policy||!ready||!!policy.revealed||finished;
    $('bp-progress').textContent=!((p.published_phases||[]).includes('blue'))?
      'Сначала заверши BLUE':!ready?'Сначала раскрой все места BLUE':
      policy?.revealed?'Очки уже показаны в эфире':
      policy?'Решение сохранено · можно показать на экране':
      'Выбери и утверди систему начисления';
    try{$('bp-help').innerHTML=previewTable(model())}catch(e){$('bp-help').textContent=e.message}
  }
  $('bp-mode').addEventListener('change',()=>{pending=null;editing=false;$('bp-confirm').classList.add('hidden');render()});
  $('bp-percent').addEventListener('input',()=>{pending=null;render()});
  $('bp-points-table').addEventListener('input',()=>{pending=null;editing=true;render()});
  $('bp-preview').addEventListener('click',async()=>{
    try{
      if(!blueReady())throw Error('Сначала закончи BLUE SHOW');
      const value=model();
      const body={kind:'blue_policy',value,expected_version:state.publication_version};
      const reply=await api('/sochi/api/admin/correction/preview','POST',body);
      pending=body;
      const d=reply.preview;
      const adjustments=(d.score_changes||[]).map(r=>
        `<tr><td>${escapeHTML(r.name)}</td><td>${fmt(r.old_total)} → ${fmt(r.new_total)}</td><td>#${r.old_place} → #${r.new_place}</td></tr>`).join('');
      $('bp-result').innerHTML=`<p class="bp-preview-title"><strong>Предпросмотр подтверждён сервером.</strong>
        Было: ${escapeHTML(d.before?.mode||'Чистые фишки')} → станет: ${escapeHTML(value.mode)}.
        ${adjustments?'<br>Изменения общего рейтинга:':''}</p>`
        +(adjustments?`<table class="bp-table"><tbody>${adjustments}</tbody></table>`:
          '<p class="muted">Изменения очков и мест не обнаружены.</p>');
      $('bp-confirm').classList.remove('hidden');
      $('bp-pin').value='';
    }catch(e){pending=null;$('bp-confirm').classList.add('hidden');toast(e.message,true)}
  });
  $('bp-confirm').addEventListener('submit',async event=>{
    event.preventDefault();
    if(!pending)return toast('Сначала проверь последствия',true);
    const pin=$('bp-pin').value, reason=$('bp-reason').value.trim();
    $('bp-pin').value='';
    try{
      const res=await api('/sochi/api/admin/correction/apply','POST',
        {...pending,pin,reason,confirm:'ИСПРАВИТЬ'});
      pending=null;editing=false;
      $('bp-confirm').classList.add('hidden');
      toast('Система начисления BLUE зафиксирована · версия '+res.version);
      await refresh();
    }catch(e){toast(e.message,true)}
  });
  $('bp-reveal').addEventListener('click',async()=>{
    if(!confirm('Показать командам назначенные ОЧКИ BLUE вместо чистых фишек?'))return;
    const ok=await change('/sochi/api/admin/publish',{action:'blue-policy-reveal'});
    if(ok)render();
  });
  document.addEventListener('sochi-admin-refreshed',()=>{
    const p=phase().blue_policy;
    if(p&&!editing){
      $('bp-mode').value=p.mode||'chips';
      $('bp-percent').value=p.percent||10;
      lastCount=0;
    }
    render();
  });
  render();
})();