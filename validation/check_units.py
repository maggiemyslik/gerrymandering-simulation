# Check after stage 02: the units table is complete and consistent with the census files.

import numpy as np
import pandas as pd

from common import RACE_GROUPS, RAW, load_units


def run(cfg):
    units = load_units(cfg)
    census = RAW / cfg["name"] / "census"
    pl = pd.read_csv(census / "pl2020_blocks.csv", dtype={"GEOID": str})

    assert units["unit_id"].is_unique, "duplicate unit ids"
    # Every person and every voting-age person in the block file lands in exactly one unit
    assert units["TOTPOP"].sum() == pl["P1_001N"].sum(), "unit population does not match the block total"
    assert units[RACE_GROUPS].sum().sum() == pl["P4_001N"].sum(), "voting-age groups do not add up to the block total"
    assert (units[RACE_GROUPS] >= 0).all().all(), "negative voting-age group count"
    print(f"PASS {cfg['name']}: {len(units)} units, population {int(units['TOTPOP'].sum())} matches the block file")

    # Reported, not failed: how much economic data is missing or top-coded, and unit sizes
    populated = units["TOTPOP"] > 0
    capped = (units["LOG_MEDINC"] == np.log(250001)).sum()
    print(f"{cfg['name']}: {int((~populated).sum())} units with no population; "
          f"income missing for {int(units.loc[populated, 'LOG_MEDINC'].isna().sum())} populated units, "
          f"degree share missing for {int(units.loc[populated, 'DEGREE_SHARE'].isna().sum())}; "
          f"{int(capped)} units at the $250,000 income cap")
    print(f"{cfg['name']}: unit population median {int(units.loc[populated, 'TOTPOP'].median())}, "
          f"max {int(units['TOTPOP'].max())}")
