import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundtrace_mvp as pipeline
from soundtrace_api import JobStore

class PipelineTests(unittest.TestCase):
    def test_demo_pipeline_produces_a_stereo_mix(self):
        environment, hum = pipeline.make_demo_inputs(duration=2)
        clean = pipeline.clean_environment(environment)
        _, backend = pipeline.extract_target(clean, "birds", Path(tempfile.gettempdir()))
        times, hz, _ = pipeline.pitch_track(hum)
        melody = pipeline.synth_melody(pipeline.correct_melody(times, hz), 2)
        mix = pipeline.arrange_mix(clean, clean, melody, 30)
        self.assertEqual(mix.shape, (30 * pipeline.SR, 2))
        self.assertTrue(np.isfinite(mix).all())
        self.assertTrue(backend.startswith("dsp_bandpass"))

    def test_job_store_round_trip(self):
        store = JobStore()
        job = store.create("birdsong", 35)
        self.assertEqual(store.get(job.id), job)
        self.assertEqual(job.status, "queued")

if __name__ == "__main__":
    unittest.main()
