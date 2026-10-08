import React from 'react';
import regions from './raster-regions.json';
const positions={vinyl:'0% 0%',tape:'100% 0%',photo:'0% 100%',mailbox:'100% 100%'};
export default function RasterArt({id,className='',label=''}){
  if(positions[id])return <span className={`raster-object ${className}`} role={label?'img':undefined} aria-label={label||undefined} aria-hidden={label?undefined:true} style={{backgroundImage:"url('/assets/ui-raster-v2/objects.png')",backgroundSize:'200% 200%',backgroundPosition:positions[id]}}/>;
  const r=regions[id];if(!r)return null;
  const [sw]=r.source,[x,y,w,h]=r.rect;
  return <span className={`raster-frame ${className}`} aria-hidden="true" style={{aspectRatio:`${w}/${h}`,'--raster-ratio':w/h}}><span className="raster-art" style={{aspectRatio:`${w}/${h}`}}><img src={r.src} alt="" draggable="false" loading="lazy" style={{width:`${sw/w*100}%`,maxWidth:'none',height:'auto',left:`${-x/w*100}%`,top:`${-y/h*100}%`}}/></span></span>;
}
