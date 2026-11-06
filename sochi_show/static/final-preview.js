'use strict';
/* Fictional only. No request to real API, no DB writes. */
const host=document.getElementById('final-stage');
const chooser=document.getElementById('demo-count');
const tie=document.getElementById('demo-tie');
const prev=document.getElementById('demo-prev');
const next=document.getElementById('demo-next');
let data=window.FinalShow.demo(11,false),step=0;
function render(){
  window.FinalShow.render(host,window.FinalShow.frame(data,step));
  document.getElementById('demo-step').textContent=step+' / 5';
  prev.disabled=step===0;next.disabled=step===5;
  next.textContent=step===4?'Чемпион →':'Далее →';
}
function reset(){data=window.FinalShow.demo(Number(chooser.value),tie.value==='yes');step=0;render()}
chooser.addEventListener('change',reset);
tie.addEventListener('change',reset);
prev.addEventListener('click',()=>{step=Math.max(0,step-1);render()});
next.addEventListener('click',()=>{step=Math.min(5,step+1);render()});
document.getElementById('demo-reset').addEventListener('click',()=>{step=0;render()});
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('keydown',e=>{
  if(e.target.matches('input,select,textarea'))return;
  if(e.key==='ArrowRight'){step=Math.min(5,step+1);render()}
  if(e.key==='ArrowLeft'){step=Math.max(0,step-1);render()}
});
render();
