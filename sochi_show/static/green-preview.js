'use strict';
/* Visual rehearsal only: all figures are illustrative. No write requests. */
const host=document.getElementById('green-stage');
const count=document.getElementById('demo-count');
const prev=document.getElementById('demo-prev');
const next=document.getElementById('demo-next');
const reset=document.getElementById('demo-reset');
let show=window.GreenShow.demo(11),step=0;
function refresh(){
  const frame=window.GreenShow.frame(show,step);
  window.GreenShow.render(host,frame);
  document.getElementById('demo-step').textContent=step+' / '+show.max_step;
  prev.disabled=step===0;
  next.disabled=step===show.max_step;
}
count.addEventListener('change',()=>{
  show=window.GreenShow.demo(Number(count.value));
  step=0;refresh();
});
prev.addEventListener('click',()=>{step=Math.max(0,step-1);refresh()});
next.addEventListener('click',()=>{step=Math.min(show.max_step,step+1);refresh()});
reset.addEventListener('click',()=>{step=0;refresh()});
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('keydown',event=>{
  if(event.target.matches('input,select,textarea'))return;
  if(event.key==='ArrowRight'){step=Math.min(show.max_step,step+1);refresh()}
  if(event.key==='ArrowLeft'){step=Math.max(0,step-1);refresh()}
});
refresh();
