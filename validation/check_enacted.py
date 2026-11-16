# Check after stage 05: every enacted map labels every unit with districts 0..k-1, and majority
# assignment moves under 1% of the state's population into a different district from the real
# map (a larger share would point to a mismatched file rather than ordinary split units).

import pandas as pd

from common import load_enacted, paths


def run(cfg):
    enacted = load_enacted(cfg)
    splits = pd.read_csv(paths(cfg)["enacted_splits"])
    for key in cfg["plan_files"]:
        labels = enacted[f"plan_{key}"]
        k = cfg["map_districts"][key]
        assert sorted(labels.unique()) == list(range(k)), f"map {key}: labels are not 0..{k - 1}"
    print(splits.to_string(index=False))
    bad = splits[splits["share_moved"] >= 0.01]
    assert bad.empty, f"maps moving 1% or more of the population:\n{bad.to_string(index=False)}"
    print(f"PASS {cfg['name']}: every map labels every unit, under 1% of people moved by split units")
    links = pd.read_csv(paths(cfg)["island_links"])
    print(f"{cfg['name']}: {len(links)} island links carrying {int(links['island_population'].sum())} people")
