(() => {
  const active=new Set();
  window.SoundTracePlayer=(src,label='聆听声音')=>{
    const box=document.createElement('div');box.className='sketch-player';
    const audio=document.createElement('audio');audio.src=src;audio.preload='metadata';audio.setAttribute('aria-label',label);
    const play=document.createElement('button');play.type='button';play.className='sketch-play';play.textContent='▶';play.setAttribute('aria-label','播放'+label);
    const body=document.createElement('div');body.className='sketch-player-body';
    const bars=document.createElement('div');bars.className='sketch-wave';bars.setAttribute('aria-hidden','true');
    for(let i=0;i<44;i++){const b=document.createElement('i');b.style.height=(9+Math.abs(Math.sin(i*1.83)*Math.cos(i*.31))*25)+'px';bars.append(b);}
    const range=document.createElement('input');range.type='range';range.min=0;range.max=1000;range.value=0;range.setAttribute('aria-label',label+'播放进度');
    const time=document.createElement('span');time.className='sketch-time';time.textContent='0:00';
    const fmt=t=>Math.floor((t||0)/60)+':'+String(Math.floor((t||0)%60)).padStart(2,'0');
    audio.onplay=()=>{active.forEach(a=>{if(a!==audio)a.pause();});active.add(audio);play.textContent='Ⅱ';play.setAttribute('aria-label','暂停'+label);};
    audio.onpause=()=>{active.delete(audio);play.textContent='▶';play.setAttribute('aria-label','播放'+label);};
    audio.ontimeupdate=()=>{range.value=Number.isFinite(audio.duration)?audio.currentTime/audio.duration*1000:0;time.textContent=fmt(audio.currentTime)+' / '+fmt(audio.duration);[...bars.children].forEach((b,i)=>{b.style.background=i/44<range.value/1000?'#09a9e4':'#d9dde1';});};
    audio.onloadedmetadata=audio.ontimeupdate;
    play.onclick=async()=>{if(audio.paused){try{await audio.play();}catch{time.textContent='暂时无法播放';}}else audio.pause();};
    range.oninput=()=>{if(Number.isFinite(audio.duration))audio.currentTime=range.value/1000*audio.duration;};
    body.append(bars,range);box.append(play,body,time,audio);return box;
  };
})();
