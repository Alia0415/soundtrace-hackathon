"""Replace the unrelated pouring-water demos with wind and birds; reuse music beds."""
from pathlib import Path
import wave
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/seeds'
RATE=32000
def read(path):
    with wave.open(str(path)) as w:
        assert w.getsampwidth()==2
        rate=w.getframerate(); channels=w.getnchannels()
        a=np.frombuffer(w.readframes(w.getnframes()),'<i2').reshape(-1,channels)/32768.
    if channels==1: a=np.repeat(a,2,axis=1)
    if rate!=RATE:
        t=np.arange(round(len(a)*RATE/rate))*rate/RATE
        a=np.column_stack([np.interp(t,np.arange(len(a)),a[:,c]) for c in range(2)])
    return a
def fit(a,n): return np.tile(a,(int(np.ceil(n/len(a))),1))[:n].copy()
def level(a,rms): return a*rms/max(1e-6,np.sqrt(np.mean(a*a)))
def fade(a,start=.6,end=2):
    a=a.copy();ni=min(len(a),int(start*RATE));no=min(len(a),int(end*RATE))
    a[:ni]*=np.linspace(0,1,ni)[:,None];a[-no:]*=np.linspace(1,0,no)[:,None]
    return a
def save(name,a):
    a*=min(1,.88/max(np.max(np.abs(a)),1e-6))
    with wave.open(str(OUT/name),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(RATE);w.writeframes((a*32767).astype('<i2').tobytes())
n=32*RATE
raw_n=16*RATE
wind=level(fit(read(ROOT/'outputs/demo_wind.wav'),raw_n),.045)
birds=level(fit(read(OUT/'seed_tape_birds.wav'),raw_n),.035)
for key,source,style in [('lakeside',wind+birds,'piano'),('lake-breeze',wind+np.roll(birds,3*RATE,axis=0)*.55,'ambient'),('evening-wind',np.roll(wind,5*RATE,axis=0),'lofi')]:
    raw=fade(level(source,.07),.25,.7)
    save('demo-raw-'+key+'.wav',raw)
    field=fit(raw,n)
    envelope=np.full(n,.32);envelope[:2*RATE]=1
    envelope[2*RATE:4*RATE]=np.linspace(1,.32,2*RATE)
    bed=np.zeros((n,2));bed[2*RATE:]=read(OUT/('demo-bed-'+style+'.wav'))[:n-2*RATE]
    save('demo-mix-'+key+'.wav',fade(field*envelope[:,None]+fade(bed,3.5,3),.25,2.5))
print('Rebuilt three scene-matched original/music pairs without pouring-water audio.')
