"""Verify the delivered demo media, not only their different filenames."""
import hashlib
import unittest
import wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    with wave.open(str(ROOT/'outputs/seeds'/name)) as w:
        rate=w.getframerate(); channels=w.getnchannels()
        data=np.frombuffer(w.readframes(w.getnframes()),'<i2').reshape(-1,channels).astype(float)/32768
    return rate,data

class DemoAudioTests(unittest.TestCase):
    def test_originals_and_finished_music_are_distinct_and_preserve_the_original_intro(self):
        hashes=set()
        for key in ['water','rain','lake','snow','birds','dusk']:
            rate,raw=load('demo-raw-'+key+'.wav');r,mix=load('demo-mix-'+key+'.wav')
            self.assertEqual(rate,r);self.assertEqual(len(raw)/rate,16);self.assertEqual(len(mix)/r,32)
            self.assertEqual(mix.shape[1],2)
            for data in [raw,mix]:
                self.assertGreater(np.sqrt(np.mean(data*data)),.01)
                self.assertLess(np.abs(data).max(),.9)
                digest=hashlib.sha256(data.tobytes()).hexdigest();self.assertNotIn(digest,hashes);hashes.add(digest)
            # Same source before the music enters; a different musical signal afterwards.
            self.assertGreater(np.corrcoef(raw[rate:2*rate].ravel(),mix[rate:2*rate].ravel())[0,1],.999)
            self.assertLess(abs(np.corrcoef(raw[6*rate:12*rate].ravel(),mix[6*rate:12*rate].ravel())[0,1]),.7)

    def test_three_music_directions_have_different_audio(self):
        digests=[]
        for style in ['piano','lofi','ambient']:
            rate,audio=load('demo-bed-'+style+'.wav')
            self.assertEqual(len(audio)/rate,32)
            self.assertGreater(np.sqrt(np.mean(audio*audio)),.03)
            digests.append(hashlib.sha256(audio.tobytes()).hexdigest())
        self.assertEqual(len(set(digests)),3)
