'use strict';
/* Always fictional demo data. No admin access or tournament database calls. */
const host=document.getElementById('secret-stage');
const prev=document.getElementById('demo-prev'),next=document.getElementById('demo-next');
const data=window.SecretShow.demo();let step=0;
function refresh(){
  window.SecretShow.render(host,window.SecretShow.frame(data,step));
  document.getElementById('demo-step').textContent=step+' / 4';
  prev.disabled=step===0;next.disabled=step===4;
  next.textContent=step===3?'Итоги →':'Раскрыть →';
}
prev.addEventListener('click',()=>{step=Math.max(0,step-1);refresh()});
next.addEventListener('click',()=>{step=Math.min(4,step+1);refresh()});
document.getElementById('demo-reset').addEventListener('click',()=>{step=0;refresh()});
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowRight'){step=Math.min(4,step+1);refresh()}
  if(e.key==='ArrowLeft'){step=Math.max(0,step-1);refresh()}
});
refresh();
