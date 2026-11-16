# Stage 03: places each year's election results on 2020 census blocks. Called by run_{state}.py.
#
# California (Statewide Database). Results are reported by SR precinct, with a conversion file
# giving each precinct's share of registered voters in every census block (PCTSRPREC, in percent).
# Each block receives that share of the precinct's votes (README, choices: precinct results onto blocks).
#   swdb_2020_block_years (2022, 2024): the conversion is to 2020 blocks, so that is the final step.
#   swdb_2010_block_years (2016 to 2020): the conversion is to 2010 blocks. Each 2010 block's votes
#   are then split across the 2020 blocks it overlaps, in proportion to shared land area, using the
#   Census 2010-to-2020 block relationship file (README, choices: California results for 2016 to 2020).
#   A 2010 block with no land (water only) is split by total shared area instead.
# Vote cells the Statewide Database leaves non-numeric (masked small counts) are counted as zero,
# and how many there are is reported.
#
# Writes one wide table, one row per 2020 block, columns {year}_{race}_D and {year}_{race}_R, and
# a totals table (votes in the source file and votes placed on 2020 blocks) for check_crosswalk.

import zipfile

import pandas as pd

from common import RAW, paths


def read_swdb(folder, name, **kwargs):
    # Files are either loose csv files or zips holding the csv alongside a readme
    if (folder / f"{name}.csv").exists():
        return pd.read_csv(folder / f"{name}.csv", **kwargs)
    with zipfile.ZipFile(folder / f"{name}.zip") as z:
        return pd.read_csv(z.open(f"{name}.csv"), **kwargs)


def precincts_to_blocks(cfg, year):
    # Returns votes on the blocks of the conversion file (2010 or 2020 blocks), and source totals
    yy = str(year)[2:]
    folder = RAW / cfg["name"] / "elections" / str(year)
    races = cfg["elections"][year]
    cols = [f"{r}{p}01" for r in races for p in ("DEM", "REP")]
    sov = read_swdb(folder, f"state_g{yy}_sov_data_by_g{yy}_srprec",
                    dtype={"SRPREC_KEY": str, "SRPREC": str}, low_memory=False)
    missing = [c for c in cols if c not in sov.columns]
    assert not missing, f"{year}: race columns not in the results file: {missing}"
    assert sov["SRPREC_KEY"].is_unique, f"{year}: precincts repeat in the results file"
    numeric = sov[cols].apply(pd.to_numeric, errors="coerce")
    masked = int((numeric.isna() & sov[cols].notna()).sum().sum())
    sov[cols] = numeric.fillna(0)
    conv = read_swdb(folder, f"state_g{yy}_sr_blk_map", dtype={"SRPREC_KEY": str, "BLOCK_KEY": str},
                     usecols=["SRPREC_KEY", "BLOCK_KEY", "PCTSRPREC"])
    # Precincts with no registered voters have no blocks in the conversion file, so their votes
    # cannot be placed; check_crosswalk reports how many votes that leaves out.
    m = conv.merge(sov[["SRPREC_KEY"] + cols], on="SRPREC_KEY", how="inner")
    m[cols] = m[cols].mul(m["PCTSRPREC"] / 100, axis=0)
    blocks = m.groupby("BLOCK_KEY")[cols].sum()
    names = {f"{r}{p}01": f"{year}_{r}_{p[0]}" for r in races for p in ("DEM", "REP")}
    totals = pd.DataFrame({"year": year, "column": [names[c] for c in cols], "source_total": sov[cols].sum().to_numpy()})
    print(f"{cfg['name']} {year}: {masked} non-numeric vote cells counted as zero")
    return blocks.rename(columns=names), totals


def blocks_2010_to_2020(cfg, votes):
    # Splits each 2010 block's votes across the 2020 blocks it overlaps, by shared land area
    with zipfile.ZipFile(RAW / cfg["name"] / "crosswalk" / f"TAB2010_TAB2020_ST{cfg['fips']}.zip") as z:
        rel = pd.read_csv(z.open(z.namelist()[0]), sep="|", dtype=str)
    rel["b10"] = rel["STATE_2010"] + rel["COUNTY_2010"] + rel["TRACT_2010"] + rel["BLK_2010"]
    rel["b20"] = rel["STATE_2020"] + rel["COUNTY_2020"] + rel["TRACT_2020"] + rel["BLK_2020"]
    land = rel["AREALAND_INT"].astype(float)
    area = land + rel["AREAWATER_INT"].astype(float)
    land_total = land.groupby(rel["b10"]).transform("sum")
    area_total = area.groupby(rel["b10"]).transform("sum")
    rel["w"] = (land / land_total).where(land_total > 0, area / area_total)
    w = rel.groupby(["b10", "b20"])["w"].sum().reset_index()
    m = w.merge(votes, left_on="b10", right_index=True, how="inner")
    cols = list(votes.columns)
    m[cols] = m[cols].mul(m["w"], axis=0)
    unmatched = set(votes.index) - set(rel["b10"])
    assert not unmatched, f"{len(unmatched)} 2010 blocks with votes are not in the Census relationship file"
    return m.groupby("b20")[cols].sum()


def run(cfg):
    tables, totals = [], []
    for year in cfg.get("swdb_2020_block_years", []) + cfg.get("swdb_2010_block_years", []):
        if not cfg["elections"][year]:
            continue
        blocks, t = precincts_to_blocks(cfg, year)
        if year in cfg.get("swdb_2010_block_years", []):
            blocks = blocks_2010_to_2020(cfg, blocks)
        t["placed_total"] = blocks[t["column"]].sum().to_numpy()
        tables.append(blocks)
        totals.append(t)
        print(f"{cfg['name']} {year}: results placed on {len(blocks)} 2020 blocks")
    p = paths(cfg)
    p["block_votes"].parent.mkdir(parents=True, exist_ok=True)
    out = pd.concat(tables, axis=1).fillna(0)
    out.index.name = "GEOID"
    out.reset_index().to_parquet(p["block_votes"], index=False)
    pd.concat(totals).sort_values(["year", "column"]).to_csv(p["vote_totals"], index=False)