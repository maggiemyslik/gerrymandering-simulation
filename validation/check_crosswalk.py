# Check after stage 03: votes are conserved when results move from precincts onto blocks.
# Fails if any race loses more than 1% of its votes, or gains any (beyond rounding).

import pandas as pd

from common import paths


def run(cfg):
    t = pd.read_csv(paths(cfg)["vote_totals"])
    t["placed_share"] = t["placed_total"] / t["source_total"]
    print(t.groupby("year")["placed_share"].agg(["min", "max"]).round(4).to_string())
    bad = t[(t["placed_share"] < 0.99) | (t["placed_share"] > 1.0001)]
    assert bad.empty, f"votes not conserved:\n{bad.to_string()}"
    print(f"PASS {cfg['name']}: every race keeps at least 99% of its votes on blocks")
