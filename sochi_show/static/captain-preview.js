'use strict';
/* Synthetic, readonly rehearsal of the visual presentation. */
const host=document.getElementById('captain-stage');
const chooser=document.getElementById('demo-count');
const all=document.getElementById('demo-all');
const render=()=>window.CaptainShow.render(host,window.CaptainShow.demo(Number(chooser.value),all.value==='yes'));
chooser.addEventListener('change',render);
all.addEventListener('change',render);
document.getElementById('demo-full').addEventListener('click',()=>{
  if(document.fullscreenElement)document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
render();
