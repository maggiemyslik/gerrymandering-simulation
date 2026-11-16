# Runs the California pipeline: every stage in order, each followed by its check, stopping at the
# first failure. Stages 06 to 09 are added once the 2010-era maps are handled descriptively.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "validation")]

from common import load_config, run_steps

run_steps(load_config("california"), [
    "00_inspect_raw",
    "02_build_units", "check_units",
    "03_crosswalk", "check_crosswalk",
    "04_attach_votes",
    "05_enacted_assignments", "check_enacted", "check_graph",
])
