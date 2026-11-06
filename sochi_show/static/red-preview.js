'use strict';
/* Completely synthetic RED preview: no database, account or external requests. */
const host=document.getElementById('red-stage');
const chooser=document.getElementById('demo-count');
const prev=document.getElementById('demo-prev');
const next=document.getElementById('demo-next');
let data=window.RedShow.demo(11),step=0;
function refresh(){
  window.RedShow.render(host,window.RedShow.frame(data,step));
  document.getElementById('demo-step').textContent=step+' / '+data.max_step;
  prev.disabled=step===0;next.disabled=step===data.max_step;
}
chooser.addEventListener('change',()=>{data=window.RedShow.demo(Number(chooser.value));step=0;refresh()});
prev.addEventListener('click',()=>{step=Math.max(0,step-1);refresh()});
next.addEventListener('click',()=>{step=Math.min(data.max_step,step+1);refresh()});
document.getElementById('demo-reset').addEventListener('click',()=>{step=0;refresh()});
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('keydown',event=>{
  if(event.target.matches('input,select,textarea'))return;
  if(event.key==='ArrowRight'){step=Math.min(data.max_step,step+1);refresh()}
  if(event.key==='ArrowLeft'){step=Math.max(0,step-1);refresh()}
});
refresh();
