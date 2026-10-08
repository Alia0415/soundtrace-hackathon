"""Run the maintained public-site UI flows against disposable databases."""
from pathlib import Path
import runpy
ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'tests/sample_browser_check.py'), run_name='__main__')
runpy.run_path(str(ROOT/'tests/selected_ui_browser_check.py'), run_name='__main__')
