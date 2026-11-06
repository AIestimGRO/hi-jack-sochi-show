'use strict';
/* Synthetic demo, deliberately no server/API access and no writes. */
const host=document.getElementById('vote-stage');
const picker=document.getElementById('demo-count'), mode=document.getElementById('demo-mode');
const back=document.getElementById('demo-prev'),next=document.getElementById('demo-next');
let data=window.VoteShow.demo(11,'target'),step=0;
function render(){
  const state=window.VoteShow.frame(data,step);
  window.VoteShow.render(host,state);
  document.getElementById('demo-step').textContent=step+' / '+state.max_step;
  back.disabled=step===0;next.disabled=step===state.max_step;
  next.textContent=step===state.count?'Итоги →':'Далее →';
}
function reset(){step=0;data=window.VoteShow.demo(Number(picker.value),mode.value);render()}
picker.addEventListener('change',reset);mode.addEventListener('change',reset);
back.addEventListener('click',()=>{step=Math.max(0,step-1);render()});
next.addEventListener('click',()=>{step=Math.min(data.all_demo_votes.length+1,step+1);render()});
document.getElementById('demo-reset').addEventListener('click',()=>{step=0;render()});
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('keydown',e=>{
  if(e.target.matches('input,select,textarea'))return;
  if(e.key==='ArrowRight'){step=Math.min(data.all_demo_votes.length+1,step+1);render()}
  if(e.key==='ArrowLeft'){step=Math.max(0,step-1);render()}
});
render();
