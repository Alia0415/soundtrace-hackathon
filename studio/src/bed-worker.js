// Original additive synthesis. No sampled music or third-party sound assets.
self.onmessage = ({data: {style, duration, diary = {}, sampleRate: sr}}) => {
  const count = Math.ceil(duration * sr), left = new Float32Array(count), right = new Float32Array(count);
  const profiles = {
    ambient:{bpm:55,pad:true,tone:.12},lofi:{bpm:76,drums:true,tone:.17,swing:.1},
    cinematic:{bpm:64,pad:true,melody:true,tone:.24},piano:{bpm:72,melody:true,tone:.1},
    folk:{bpm:88,arp:true,tone:.35},jazz:{bpm:92,melody:true,drums:true,swing:.22,tone:.2},
    electronic:{bpm:112,arp:true,drums:true,tone:.5},orchestral:{bpm:68,pad:true,melody:true,tone:.32},
    rock:{bpm:104,melody:true,drums:true,tone:.65},world:{bpm:86,arp:true,drums:true,tone:.42},
  };
  const profile = profiles[style] || profiles.ambient;
  const bright = ['happy','excited','hopeful'].includes(diary.mood);
  const chords = bright ? [[48,55,60,64],[45,52,57,60],[41,48,53,57],[43,50,55,59]] : [[48,55,58,63],[45,52,55,60],[41,48,52,56],[43,50,55,58]];
  if (style === 'jazz') chords.forEach(chord=>chord.push(chord[0]+10));
  const pace = (['exercise','gathering'].includes(diary.activity)?1.12:['home','study'].includes(diary.activity)?.92:1) * (['rainy','snowy'].includes(diary.weather)?.94:1);
  const beat = 60 / (profile.bpm * pace);
  const bar = beat * 4, tau = 2 * Math.PI;
  let seed = 9147;
  const noise = () => { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 2147483648 - 1; };
  function note(midi, at, length, amp, pan, pad = false) {
    const f = 440 * 2 ** ((midi - 69) / 12), start = Math.floor(at * sr), len = Math.min(Math.floor(length * sr), count - start);
    for (let j = 0; j < len; j++) {
      const t = j / sr, env = pad ? Math.min(1,t/.7)*Math.min(1,(length-t)/1.1) : Math.min(1,t/.008)*Math.exp(-t/1.25)*Math.min(1,(length-t)/.12);
      const x = amp * env * (Math.sin(tau*f*t) + profile.tone*Math.sin(tau*f*2*t)*Math.exp(-t*2) + profile.tone*.35*Math.sin(tau*f*3*t));
      left[start+j] += x * Math.sqrt((1-pan)/2); right[start+j] += x * Math.sqrt((1+pan)/2);
    }
  }
  for (let at = 0, barIndex = 0; at < duration; at += bar, barIndex++) {
    const chord = chords[barIndex % chords.length];
    chord.forEach((m, i) => note(m, at + (profile.pad ? i*.08 : i*.025), profile.pad ? bar+1 : bar, .06, (i-(chord.length-1)/2)*.22, profile.pad));
    if(profile.melody) for(let s=0;s<4;s++) note(chord[[2,3,1,3][s]]+12,at+(s+(s%2?profile.swing||0:0))*beat,Math.min(2,bar),.065,s%2?.35:-.35);
    if(profile.arp) for(let s=0;s<8;s++) note(chord[s%chord.length]+(s%3===0?12:0),at+s*beat/2,beat*1.5,.065,s%2?.25:-.25);
    if(profile.drums) note(chord[0]-12,at,bar,.07,0);
    if (profile.drums) for (let b=0;b<4;b++) {
      const start = Math.floor((at+b*beat)*sr);
      for (let j=0;j<sr*.22 && start+j<count;j++) {
        const t=j/sr, kick=b%2===0 ? .13*Math.sin(tau*(48*t+2.5*(1-Math.exp(-t*25))))*Math.exp(-t*22) : .04*noise()*Math.exp(-t*35);
        left[start+j]+=kick; right[start+j]+=kick;
      }
    }
  }
  for(let i=0;i<count;i++) { const fade=Math.min(1,i/sr/.6,(count-i)/sr/1.5); left[i]*=fade;right[i]*=fade; }
  self.postMessage([left,right],[left.buffer,right.buffer]);
};
