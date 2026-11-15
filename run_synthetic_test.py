# Tests stages 06 to 09 and their checks on a fake 30 x 30 grid state, before real data exists.
# Writes only synthetic_* files and figures, never touching real data. No arguments:
#   python run_synthetic_test.py

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent / d) for d in ("src", "validation")]
from common import load_config, run_steps  # noqa: E402

STEPS = [
    "make_synthetic_state",   # fake units, graph, enacted maps, in the stage 05 output format
    "check_graph",
    "06_run_ensemble",
    "check_ensemble",
    "07_score_plans",
    "check_scores",
    "08_recentre",
    "check_recentre",
    "09_descriptives",
]

# The guard stops the parallel chain processes from re-running the pipeline when they start
if __name__ == "__main__":
    run_steps(load_config("synthetic"), STEPS)
