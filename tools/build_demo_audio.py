"""Build clearly separated, pre-produced demo originals, music beds and finished mixes.

Usage: python tools/build_demo_audio.py path/to/licensed-instrumental.wav
Requires numpy/scipy for authoring only; deployed pages serve the committed WAV files.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly, butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/seeds'
RATE = 32000
rng = np.random.default_rng(20261009)

def read(path):
    rate, a = wavfile.read(path)
    if a.dtype.kind == 'i': a = a.astype(float) / np.iinfo(a.dtype).max
    if a.ndim == 1: a = np.column_stack([a, a])
    return resample_poly(a, RATE, rate)

def fit(a, n):
    return np.tile(a, (int(np.ceil(n/len(a))), 1))[:n].copy()

def level(a, rms):
    return a * (rms / max(1e-6, np.sqrt(np.mean(a*a))))

def fade(a, start=.6, end=2):
    a=a.copy(); ni=min(len(a),int(start*RATE)); no=min(len(a),int(end*RATE))
    a[:ni]*=np.linspace(0,1,ni)[:,None];a[-no:]*=np.linspace(1,0,no)[:,None]
    return a

def save(name, a):
    peak=np.max(np.abs(a)); a=a*min(1,.88/max(peak,1e-6))
    wavfile.write(OUT/name,RATE,(np.clip(a,-1,1)*32767).astype('<i2'))

def build(source):
    music=read(source)
    if len(music)<125*RATE: raise ValueError('Use the complete instrumental (at least 125 seconds).')
    n=32*RATE; raw_n=16*RATE
    piano=level(music[:n],.14)
    lofi=level(sosfilt(butter(2,4800,fs=RATE,output='sos'),music[40*RATE:40*RATE+n],axis=0),.12)
    # A quiet swung rhythm makes this prepared arrangement audibly different.
    for beat in np.arange(0,32,60/80):
        start=int(beat*RATE); t=np.arange(min(int(.20*RATE),n-start))/RATE
        kick=np.sin(2*np.pi*(48*t+5*(1-np.exp(-22*t))))*np.exp(-25*t)*.18
        lofi[start:start+len(t)]+=kick[:,None]
        h=int((beat+.375)*RATE)
        if h<n:
            hit=rng.normal(0,.016,min(int(.06*RATE),n-h))*np.exp(-np.arange(min(int(.06*RATE),n-h))/RATE*65)
            lofi[h:h+len(hit)]+=hit[:,None]
    ambient=level(sosfilt(butter(2,2200,fs=RATE,output='sos'),music[90*RATE:90*RATE+n],axis=0),.11)
    for delay,gain in [(int(.37*RATE),.18),(int(.71*RATE),.1)]: ambient[delay:]+=ambient[:-delay]*gain
    beds={'piano':fade(piano),'lofi':fade(lofi),'ambient':fade(ambient)}
    for key,a in beds.items(): save('demo-bed-'+key+'.wav',a)
    water=fit(read(OUT/'seed_tape_water.wav'),raw_n)
    birds=fit(read(OUT/'seed_tape_birds.wav'),raw_n)
    wind=fit(read(ROOT/'outputs/demo_wind.wav'),raw_n)
    rain=rng.normal(0,1,(raw_n,2));rain=sosfilt(butter(2,[650,6500],btype='bandpass',fs=RATE,output='sos'),rain,axis=0)
    originals=[water,rain,np.roll(water,3*RATE,axis=0)*.7+wind*.25,wind,birds,np.roll(wind,5*RATE,axis=0)*.7+water*.2]
    keys=['water','rain','lake','snow','birds','dusk'];arrangements=['piano','lofi','ambient','ambient','piano','lofi']
    for i,(key,a,style) in enumerate(zip(keys,originals,arrangements)):
        raw=fade(level(a,.07),.25,.7); save('demo-raw-'+key+'.wav',raw)
        field=fit(raw,n); envelope=np.full(n,.32);envelope[:2*RATE]=1
        envelope[2*RATE:4*RATE]=np.linspace(1,.32,2*RATE)
        bed=np.zeros((n,2)); excerpt=beds[style]
        # First two seconds are the same original: the transition tells the story.
        bed[2*RATE:]=excerpt[:n-2*RATE]; bed=fade(bed,3.5,3)
        save('demo-mix-'+key+'.wav',fade(field*envelope[:,None]+bed,.25,2.5))
    print('Built 6 original/music pairs and 3 arrangement beds (32 seconds, stereo).')

if __name__=='__main__':
    build(Path(sys.argv[1]))
    import runpy
    runpy.run_path(str(Path(__file__).with_name('fix_lakeside_demo.py')))
