import React, {useId} from 'react';
import './memory-glass.css';

// Local SVG paint servers keep every carried/cabinet copy independent.
export default function MemoryGlass({color='#92d5bf'}) {
  const id=useId().replace(/:/g,'');
  const paint=name=>`url(#${id}-${name})`;
  const body='M48 54 C47 76 25 81 24 116 L24 206 C24 233 43 246 90 246 C137 246 156 233 156 206 L156 116 C155 81 133 76 132 54 Z';
  return <span className="bottle memory-glass" aria-hidden="true">
    <svg viewBox="0 0 180 270" fill="none">
      <defs>
        <linearGradient id={`${id}-shell`} x1="24" y1="150" x2="156" y2="150" gradientUnits="userSpaceOnUse"><stop stopColor="#d7fff0" stopOpacity=".85"/><stop offset=".09" stopColor="#183f40" stopOpacity=".5"/><stop offset=".2" stopColor="#b4e8db" stopOpacity=".35"/><stop offset=".48" stopColor="#123f39" stopOpacity=".12"/><stop offset=".76" stopColor="#d4ffe1" stopOpacity=".3"/><stop offset=".92" stopColor="#154c49" stopOpacity=".55"/><stop offset="1" stopColor="#f1ffe9" stopOpacity=".9"/></linearGradient>
        <radialGradient id={`${id}-garden`} cx=".45" cy=".8" r=".8"><stop stopColor="#f1ffb2" stopOpacity=".9"/><stop offset=".38" stopColor={color} stopOpacity=".8"/><stop offset="1" stopColor="#1a5851" stopOpacity=".18"/></radialGradient>
        <linearGradient id={`${id}-rim`} x1="43" x2="137" gradientUnits="userSpaceOnUse"><stop stopColor="#e9ffdd"/><stop offset=".17" stopColor="#528679"/><stop offset=".42" stopColor="#e7ffe7"/><stop offset=".64" stopColor="#739e88"/><stop offset=".85" stopColor="#f2ffe9"/><stop offset="1" stopColor="#3b7165"/></linearGradient>
        <linearGradient id={`${id}-shine`} x1="34" y1="95" x2="70" y2="220" gradientUnits="userSpaceOnUse"><stop stopColor="white" stopOpacity=".9"/><stop offset=".45" stopColor="#e9fff7" stopOpacity=".1"/><stop offset="1" stopColor="white" stopOpacity=".65"/></linearGradient>
        <radialGradient id={`${id}-halo`}><stop stopColor="#fffbc4" stopOpacity=".85"/><stop offset="1" stopColor="#ecffb2" stopOpacity="0"/></radialGradient>
        <clipPath id={`${id}-inside`}><path d={body}/></clipPath>
        <filter id={`${id}-bloom`} x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.2"/></filter>
      </defs>
      <ellipse cx="90" cy="254" rx="60" ry="9" fill="#123d3c" opacity=".28"/>
      <ellipse cx="90" cy="250" rx="43" ry="4" fill={color} opacity=".4"/>
      <path d={body} fill={paint('shell')} stroke="#e3ffed" strokeOpacity=".65" strokeWidth="1.4"/>
      <g clipPath={paint('inside')}>
        <path d="M26 132 Q70 105 111 127 T160 124 V247 H24Z" fill={paint('garden')}/>
        <ellipse cx="89" cy="220" rx="66" ry="25" fill={color} opacity=".28"/>
        <path d="M28 224 Q44 203 64 222 Q81 198 99 217 Q131 198 153 220 L157 250 H25Z" fill="#638a62" opacity=".64"/>
        <path d="M29 232 Q61 214 86 232 Q119 211 154 228" stroke="#d0e6a0" strokeWidth="8" opacity=".55"/>
        <g className="jar-fern" stroke="#bddb8a" strokeWidth="1.3" strokeLinecap="round">
          <path d="M118 231 Q108 182 123 143 M55 232 Q65 203 51 177"/>
          {[0,1,2,3,4].map(i=><g key={i}><path d={`M${116-i*.2} ${213-i*13} q-17 -2 -18 -13 q16 1 18 13`} fill={i%2?'#a8ce83':'#74ab80'}/><path d={`M${116+i*.6} ${206-i*12} q16 -5 16 -15 q-14 3 -16 15`} fill="#91c48c"/></g>)}
          <path d="M58 220 Q42 221 40 209 Q53 208 58 220 M59 208 Q73 202 71 192 Q60 197 59 208 M57 197 Q43 194 44 184 Q54 185 57 197" fill="#a7cf99"/>
        </g>
        <g className="jar-stardust">
          <path d="M71 216 C137 177 132 140 90 143 C47 146 60 191 91 174 C114 161 87 150 78 162" stroke="#efffd2" strokeOpacity=".7" strokeWidth="1.1"/>
          <path d="M58 211 C25 171 57 134 104 120" stroke="#fffbc6" strokeOpacity=".6" strokeWidth=".8"/>
          {[[60,133],[118,174],[45,193],[102,211],[76,110],[130,203],[43,153],[84,224],[105,97],[67,201],[135,134]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i%3===0?1.8:.9} fill="#fffed0"/>) }
        </g>
        {[[81,165,1],[122,126,.75],[51,204,.6]].map(([x,y,s],i)=><g key={i} className={`jar-star jar-star-${i}`} style={{transformOrigin:`${x}px ${y}px`}}><circle cx={x} cy={y} r={25*s} fill={paint('halo')}/><path d="M0 -15 L4 -4 L15 0 L4 4 L0 15 L-4 4 L-15 0 L-4 -4Z" transform={`translate(${x} ${y}) scale(${s})`} fill="#fffed3" filter={paint('bloom')}/><path d="M0 -12 L3 -3 L12 0 L3 3 L0 12 L-3 3 L-12 0 L-3 -3Z" transform={`translate(${x} ${y}) scale(${s})`} fill="#fffde0"/></g>)}
        <path d="M42 91 Q31 105 32 142 L34 203 Q35 222 43 226 L42 170 Q38 124 49 92Z" fill={paint('shine')}/>
        <path d="M139 95 Q150 112 147 163 L144 204 Q142 220 135 225" stroke="#eaffed" strokeOpacity=".65" strokeWidth="3" strokeLinecap="round"/>
        <path d="M49 96 Q85 77 126 96 M35 228 Q85 249 143 226" stroke="#eaffef" strokeOpacity=".48" strokeWidth="2"/>
        <path d="M51 107 L119 89 M40 119 L86 105" stroke="white" strokeOpacity=".24" strokeWidth="1.5"/>
      </g>
      <ellipse cx="90" cy="55" rx="44" ry="14" fill="#193f36" fillOpacity=".5" stroke={paint('rim')} strokeWidth="5"/>
      <path d="M46 51 V67 C48 85 132 85 134 67 V51" fill={paint('shell')} stroke={paint('rim')} strokeWidth="3"/>
      <ellipse cx="90" cy="49" rx="45" ry="15" fill="#4a7764" fillOpacity=".3" stroke={paint('rim')} strokeWidth="5"/>
      <ellipse cx="90" cy="49" rx="38" ry="10" fill="#163f3a" fillOpacity=".4" stroke="#efffe1" strokeOpacity=".6" strokeWidth="1.4"/>
      <path d="M49 65 Q88 84 132 65 M53 42 Q70 33 94 35" stroke="#f0ffdd" strokeOpacity=".85" strokeWidth="2" strokeLinecap="round"/>
      <path d="M43 237 Q87 258 138 236" stroke="#eaffef" strokeOpacity=".7" strokeWidth="3"/>
    </svg>
  </span>;
}
