# Downloads the Texas Census data that can be fetched by script (TIGER/Line 2020 blocks and
# block groups, PL 94-171 blocks, ACS block groups) into data/raw/texas/census/. Run once;
# everything else is downloaded by hand (README). 
#   python download_texas.py

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent / d) for d in ("src", "validation")]
from common import load_config, run_steps  

if __name__ == "__main__":
    run_steps(load_config("texas"), ["01_download"])
