'use strict';
/* HI JACK / SOCHI — proportional allocation of real final-table chips.
   BLUE clean-chip places are immutable. Bonuses are separate physical chips.
   A PIN-confirmed preview is mandatory; the director reveals stacks later.
 */
(()=>{
  const $=id=>document.getElementById(id);
  const fmt=n=>new Intl.NumberFormat('ru-RU').format(n??0);
  const escapeHTML=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let pending=null;
  const phase=()=>state?.published||{};
  const blueReady=()=>{
    const p=phase(),show=p.blue_show;
    return (p.published_phases||[]).includes('blue')
      &&show&&show.step>=show.ranking.length+1;
  };
  const rows=()=>{
    const p=phase();
    const names=new Map((state?.teams||[]).map(t=>[t.team_id,t.display_name]));
    const all=Object.entries(p.stages||{}).filter(([id,r])=>
      Number.isSafeInteger(r.blue_net_chips) && Number.isSafeInteger(r.survivor_bonus))
      .map(([id,r])=>({id:Number(id),
        name:names.get(Number(id))||'Команда №'+id,
        net:r.blue_net_chips,survivors:r.survivor_bonus}));
    all.sort((a,b)=>b.net-a.net||a.id-b.id);
    all.forEach((r,i)=>r.place=i&&r.net===all[i-1].net?all[i-1].place:i+1);
    return all;
  };
  const stacks=arr=>{
    if(!arr.length)return {};
    const vals=arr.map(r=>r.net),lo=Math.min(...vals),hi=Math.max(...vals);
    const map={};
    for(const r of arr){
      if(lo===hi){map[r.id]=550000;continue}
      const raw=100000+Math.floor((900000*(r.net-lo)*2+(hi-lo))/(2*(hi-lo)));
      map[r.id]=Math.max(100000,Math.min(1000000,Math.floor((raw+500)/1000)*1000));
    }
    return map;
  };
  const previewTable=()=>{
    const list=rows(),count=state?.team_count||0;
    if(!list.length||list.length!==count)
      return '<p class="muted">После опубликованного BLUE здесь появятся чистые фишки всех команд.</p>';
    const chipMap=stacks(list);
    const arr=list.map(r=>({...r,starting:chipMap[r.id]}));
    return `<div class="bp-summary"><strong>Минимум: 100 000 · Максимум: 1 000 000</strong>
      <span>Пропорциональный диапазон: 900 000 фишек</span>
      <span>Округление до 1 000</span></div>
      <table class="bp-table"><thead><tr><th>Место BLUE</th><th>Команда</th>
        <th>Чистые фишки BLUE</th><th>Стартовый стек RED</th>
        <th>Выжили · бонус</th><th>К выдаче капитану</th></tr></thead>
      <tbody>${arr.map(r=>`<tr class="${r.place===1?'bp-leading':''}">
        <td>#${r.place}</td><td>${escapeHTML(r.name)}</td><td>${fmt(r.net)}</td>
        <td><strong>${fmt(r.starting)}</strong></td><td>+${fmt(r.survivors)}</td>
        <td><strong>${fmt(r.starting+r.survivors)}</strong></td></tr>`).join('')}</tbody></table>
      <p class="muted"><strong>Важно:</strong> +5 000 за выбитого Secret Jack и +10 000 за голос
        будут добавляться <em>после</em> объявления стартовых стеков. Чистые фишки BLUE и
        места BLUE не меняются.</p>`;
  };
  function render(){
    if(!$('bp-progress'))return;
    const p=phase(),policy=p.blue_policy||null,ready=blueReady();
    const red=(p.published_phases||[]).includes('red');
    $('bp-help').innerHTML=previewTable();
    $('bp-preview').disabled=!ready;
    $('bp-reveal').disabled=!ready||red||!policy||policy.mode!=='final_table'||!!policy.revealed;
    $('bp-progress').textContent=!((p.published_phases||[]).includes('blue'))
      ?'Сначала опубликуй BLUE'
      :!ready?'Сначала раскрой все места BLUE'
      :policy?.mode==='final_table'&&policy.revealed
        ?'Стартовые стеки объявлены · переходи к Secret Jack и голосам'
        :policy?.mode==='final_table'
          ?'Распределение сохранено · можно объявить стеки'
          :'Рассчитай и утверди распределение для финального стола';
  }
  $('bp-preview').addEventListener('click',async()=>{
    try{
      if(!blueReady())throw Error('Сначала заверши показ всех мест BLUE');
      const body={kind:'blue_policy',value:{mode:'final_table'},
                  expected_version:state.publication_version};
      const data=await api('/sochi/api/admin/correction/preview','POST',body);
      pending=body;
      const d=data.preview||{};
      $('bp-result').innerHTML='<p class="bp-preview-title"><strong>Сервер проверил пропорции.</strong> '+
        'Таблица выше показывает фактические стеки. Изменение затронет фишки для финального стола, не места BLUE.</p>';
      $('bp-confirm').classList.remove('hidden');
      $('bp-pin').value='';
    }catch(e){
      pending=null;
      $('bp-confirm').classList.add('hidden');
      toast(e.message,true);
    }
  });
  $('bp-confirm').addEventListener('submit',async event=>{
    event.preventDefault();
    if(!pending)return toast('Сначала рассчитай и проверь стеки',true);
    const pin=$('bp-pin').value,reason=$('bp-reason').value.trim();
    $('bp-pin').value='';
    try{
      if(reason.length<8)throw Error('Укажи причину (минимум 8 символов)');
      const result=await api('/sochi/api/admin/correction/apply','POST',{
        ...pending,pin,reason,confirm:'ИСПРАВИТЬ'
      });
      pending=null;
      $('bp-confirm').classList.add('hidden');
      toast('Фишки финального стола утверждены · версия '+result.version);
      await refresh();
    }catch(e){toast(e.message,true)}
  });
  $('bp-reveal').addEventListener('click',async()=>{
    if(!confirm('Объявить стартовые стеки 100 000–1 000 000 на проекторе? Фишки готовы к выдаче капитанам.'))return;
    await change('/sochi/api/admin/publish',{action:'blue-policy-reveal'});
  });
  document.addEventListener('sochi-admin-refreshed',render);
  render();
})();