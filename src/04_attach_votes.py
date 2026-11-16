# Stage 04: adds each year's block-level results to the units table. Called by run_{state}.py.
# California: a block belongs to the block group whose GEOID begins its own, so block group
# totals are exact sums of block totals. Units with no votes in a race get 0.

import pandas as pd

from common import load_units, paths


def run(cfg):
    p = paths(cfg)
    units = load_units(cfg)
    votes = pd.read_parquet(p["block_votes"])
    votes["unit_id"] = votes["GEOID"].str[:12]
    by_unit = votes.drop(columns="GEOID").groupby("unit_id").sum()
    unplaced = set(by_unit.index) - set(units["unit_id"])
    assert not unplaced, f"{len(unplaced)} blocks with votes belong to no unit"
    units = units.merge(by_unit, left_on="unit_id", right_index=True, how="left")
    units[by_unit.columns] = units[by_unit.columns].fillna(0)
    units.to_parquet(p["units"], index=False)
    print(f"{cfg['name']}: {len(by_unit.columns)} vote columns added to {len(units)} units")
