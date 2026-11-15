# California pipeline: every stage in order, each followed by its check; a failed check stops the
# run. Starts from the raw files in data/raw/california/. No arguments:
#   python run_california.py

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent / d) for d in ("src", "validation")]
from common import load_config, run_steps  # noqa: E402

STEPS = [
    "00_inspect_raw",   # lists every raw file's columns and first rows: outputs/raw_inspection_california.txt
    # Stages 02 to 05 and their checks are added here once written, then:
    # 06_run_ensemble, check_ensemble, 07_score_plans, check_scores,
    # 08_recentre, check_recentre, 09_descriptives
]

# The guard stops the parallel chain processes from re-running the pipeline when they start
if __name__ == "__main__":
    run_steps(load_config("california"), STEPS)
