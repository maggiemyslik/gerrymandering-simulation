# Stage 02: builds the units table and unit geometry for one state. Called by run_{state}.py.
# California: units are 2020 census block groups (README, choices: unit of analysis).
# Texas: units are VTDs; written once the Texas raw files have been inspected.
#
# Every unit gets (README, data contract):
#   TOTPOP          2020 census total population, summed from blocks
#   COUNTY          county FIPS code (used by the ensemble's county-split penalty)
#   VAP_HISP, VAP_NHWHITE, VAP_NHBLACK, VAP_NHASIAN   voting-age population (18+) by group, from blocks
#   VAP_OTHER       all remaining voting-age population (18+ total minus the four groups above)
#   LOG_MEDINC      log of ACS median household income; missing where the ACS suppresses it.
#                   The ACS codes "250,000 or more" as 250,001, kept as is (README, choices: income)
#   DEGREE_SHARE    share of adults 25+ with a bachelor's degree or higher; missing where there are none
# Units are ordered by GEOID, and idx is the row number 0..n-1.

import geopandas as gpd
import numpy as np
import pandas as pd

from common import RAW, paths


def run(cfg):
    assert cfg["unit_type"] == "block_group", f"unit type {cfg['unit_type']} is written once its raw files are inspected"
    census = RAW / cfg["name"] / "census"
    fips = cfg["fips"]

    geo = gpd.read_file(census / f"tl_2020_{fips}_bg.zip", columns=["GEOID", "COUNTYFP"])
    geo = geo.sort_values("GEOID").reset_index(drop=True).to_crs(cfg["crs_projected"])
    units = pd.DataFrame({"idx": np.arange(len(geo)), "unit_id": geo["GEOID"], "COUNTY": geo["COUNTYFP"].astype(int)})

    # Block counts, summed to block groups (a block's GEOID begins with its block group's)
    pl = pd.read_csv(census / "pl2020_blocks.csv", dtype={"GEOID": str})
    pl["unit_id"] = pl["GEOID"].str[:12]
    bg = pl.groupby("unit_id")[["P1_001N", "P4_001N", "P4_002N", "P4_005N", "P4_006N", "P4_008N"]].sum()
    units = units.merge(bg, left_on="unit_id", right_index=True, how="left")
    units[bg.columns] = units[bg.columns].fillna(0)
    units["TOTPOP"] = units["P1_001N"]
    units["VAP_HISP"] = units["P4_002N"]
    units["VAP_NHWHITE"] = units["P4_005N"]
    units["VAP_NHBLACK"] = units["P4_006N"]
    units["VAP_NHASIAN"] = units["P4_008N"]
    units["VAP_OTHER"] = units["P4_001N"] - units[["P4_002N", "P4_005N", "P4_006N", "P4_008N"]].sum(axis=1)
    units = units.drop(columns=bg.columns)

    # ACS: negative values are the Census's codes for suppressed or unavailable estimates
    acs = pd.read_csv(census / f"acs{cfg['acs_year']}_bg.csv", dtype={"GEOID": str}).set_index("GEOID")
    acs = acs.where(acs >= 0)
    medinc = acs["B19013_001E"].where(acs["B19013_001E"] > 0)
    degree = acs[["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]].sum(axis=1, min_count=4)
    adults = acs["B15003_001E"].where(acs["B15003_001E"] > 0)
    units["LOG_MEDINC"] = np.log(units["unit_id"].map(medinc)).to_numpy()
    units["DEGREE_SHARE"] = units["unit_id"].map(degree / adults).to_numpy()

    p = paths(cfg)
    p["units"].parent.mkdir(parents=True, exist_ok=True)
    units.to_parquet(p["units"], index=False)
    gpd.GeoDataFrame(units[["unit_id", "idx"]], geometry=geo.geometry).to_parquet(p["units_geo"], index=False)
    print(f"{cfg['name']}: {len(units)} units, population {int(units['TOTPOP'].sum())}")
