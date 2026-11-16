# Stage 01: downloads everything that can be fetched by script, all from the US Census Bureau.
# Called by download_{state}.py.
# Every other source needs a login, an extract request or a portal click; those are downloaded
# by hand following the README into the same data/raw/{state}/ folders.
#
# Per state, into data/raw/{state}/census/:
#   tl_2020_{fips}_tabblock20.zip   TIGER/Line 2020 census blocks: geometry and total population (POP20)
#   tl_2020_{fips}_bg.zip           TIGER/Line 2020 block groups: geometry
#   pl2020_blocks.csv               2020 census redistricting data, one row per block (Census API):
#                                     P1_001N  total population
#                                     P4_001N  population 18+ (voting-age population, VAP)
#                                     P4_002N  Hispanic or Latino, 18+
#                                     P4_005N  not Hispanic, White alone, 18+
#                                     P4_006N  not Hispanic, Black alone, 18+
#                                     P4_008N  not Hispanic, Asian alone, 18+
#                                   Blocks, not block groups, so the counts add up exactly into
#                                   Texas VTDs as well as California block groups.
#   (and into data/raw/{state}/plans/2010/)
#   BlockAssign_ST{fips}_{postal}_CD.txt   2020 census blocks assigned to the congressional districts
#                                   in force in 2020 (116th Congress): California's 2011 Commission map,
#                                   Texas's 2013 court-adopted map. From the Census Bureau's 2020 block
#                                   assignment files, unchanged. 2020 blocks were drawn to follow these
#                                   district lines, so each block sits in one district and the 2010-era
#                                   map needs no 2010-to-2020 crosswalk.
#   (California only, for each year in swdb_2010_block_years, into data/raw/california/elections/{year}/)
#   state_g{yy}_sov_data_by_g{yy}_srprec.zip   Statewide Database precinct results
#   state_g{yy}_sr_blk_map.zip      Statewide Database precinct-to-2010-block conversion
#   (and into data/raw/{state}/crosswalk/)
#   TAB2010_TAB2020_ST{fips}.zip    Census 2010-to-2020 block relationship file, with the land area
#                                   each 2010 block shares with each 2020 block
#   acs{year}_bg.csv                ACS 5-year estimates, one row per block group (Census API):
#                                     B19013_001E  median household income
#                                     B15003_001E  population 25+
#                                     B15003_022E to _025E  bachelor's, master's, professional, doctorate
#                                   Block groups are the finest level the ACS publishes. Suppressed
#                                   values come through as the Census codes (e.g. -666666666) and are
#                                   handled when the units are built, not here.
#
# The API key is read from .env (one line: CENSUS_API_KEY=...). Both CSVs keep a GEOID column as
# text, so later stages must read it with dtype=str to keep the leading zero.

import io
import zipfile

import geopandas as gpd
import pandas as pd
import requests

from common import RAW, ROOT

TIGER = "https://www2.census.gov/geo/tiger/TIGER2020"
BAF = "https://www2.census.gov/geo/docs/maps-data/data/baf2020"
REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/t10t20"
SWDB = "https://statewidedatabase.org/pub/data"
API_PL = "https://api.census.gov/data/2020/dec/pl"
API_ACS = "https://api.census.gov/data/{year}/acs/acs5"
PL_VARS = ["P1_001N", "P4_001N", "P4_002N", "P4_005N", "P4_006N", "P4_008N"]
ACS_VARS = ["B19013_001E", "B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]


def api_key():
    # .env holds one line, CENSUS_API_KEY=...; read directly so no extra package is needed
    lines = (ROOT / ".env").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)["CENSUS_API_KEY"].strip()


def census_get(session, url, variables, geo_for, geo_in, key):
    # One API request; returns a DataFrame with the variables plus the geography columns.
    # The API answers a bad request with an HTML page rather than an error code, so the
    # check is that the reply is a JSON table, which starts with "[".
    r = session.get(url, params={"get": ",".join(variables), "for": geo_for, "in": geo_in, "key": key},
                    timeout=120)
    r.raise_for_status()
    shown = r.url.replace(key, "KEY")
    assert r.text.startswith("["), f"Census API sent a page, not data; open this in a browser to read it:\n{shown}"
    rows = r.json()
    return pd.DataFrame(rows[1:], columns=rows[0])


def download(url, dest):
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"  {dest.name}: {len(r.content) / 1e6:.1f} MB")


def download_2010_era_plan(cfg, pl_blocks):
    # Keeps only the congressional district file from the state's block assignment zip
    fips, postal = cfg["fips"], cfg["postal"]
    name = f"BlockAssign_ST{fips}_{postal}_CD.txt"
    r = requests.get(f"{BAF}/BlockAssign_ST{fips}_{postal}.zip", timeout=600)
    r.raise_for_status()
    text = zipfile.ZipFile(io.BytesIO(r.content)).read(name)
    out = RAW / cfg["name"] / "plans" / "2010"
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(text)
    plan = pd.read_csv(io.BytesIO(text), sep="|", dtype=str)
    # Checks: the right era's map (53 districts in California, 36 in Texas, from the config),
    # and every 2020 block assigned exactly once
    k = plan["DISTRICT"].nunique()
    assert k == cfg["map_districts"]["2010"], f"{name} has {k} districts, config expects {cfg['map_districts']['2010']}"
    assert plan["BLOCKID"].is_unique and set(plan["BLOCKID"]) == set(pl_blocks), f"{name} does not cover every 2020 block once"
    print(f"  {name}: {len(plan)} blocks in {k} districts (every block assigned once)")


def download_2010_block_elections(cfg):
    # Statewide Database files for elections whose precinct conversions are on 2010 blocks,
    # plus the Census crosswalk that moves 2010 blocks onto 2020 blocks. Files are kept zipped.
    for year in cfg.get("swdb_2010_block_years", []):
        yy = str(year)[2:]
        out = RAW / cfg["name"] / "elections" / str(year)
        out.mkdir(parents=True, exist_ok=True)
        for name in [f"state_g{yy}_sov_data_by_g{yy}_srprec.zip", f"state_g{yy}_sr_blk_map.zip"]:
            download(f"{SWDB}/G{yy}/state/{name}", out / name)
    if cfg.get("swdb_2010_block_years"):
        out = RAW / cfg["name"] / "crosswalk"
        out.mkdir(parents=True, exist_ok=True)
        name = f"TAB2010_TAB2020_ST{cfg['fips']}.zip"
        download(f"{REL}/{name}", out / name)


def run(cfg):
    fips, year = cfg["fips"], cfg["acs_year"]
    out = RAW / cfg["name"] / "census"
    out.mkdir(parents=True, exist_ok=True)
    print(cfg["name"])
    download(f"{TIGER}/TABBLOCK20/tl_2020_{fips}_tabblock20.zip", out / f"tl_2020_{fips}_tabblock20.zip")
    download(f"{TIGER}/BG/tl_2020_{fips}_bg.zip", out / f"tl_2020_{fips}_bg.zip")

    key = api_key()
    s = requests.Session()
    # Block and block group requests must name one county at a time, so get the county list first
    counties = census_get(s, API_PL, ["NAME"], "county:*", f"state:{fips}", key)["county"].tolist()
    print(f"  {len(counties)} counties")

    pl, acs = [], []
    for i, c in enumerate(counties, 1):
        pl.append(census_get(s, API_PL, PL_VARS, "block:*", f"state:{fips} county:{c} tract:*", key))
        acs.append(census_get(s, API_ACS.format(year=year), ACS_VARS, "block group:*",
                              f"state:{fips} county:{c} tract:*", key))
        if i % 25 == 0 or i == len(counties):
            print(f"  counties done: {i} of {len(counties)}", flush=True)

    # GEOID: state + county + tract + block (15 digits), or + block group (12 digits)
    pl = pd.concat(pl, ignore_index=True)
    pl.insert(0, "GEOID", pl["state"] + pl["county"] + pl["tract"] + pl["block"])
    pl = pl[["GEOID"] + PL_VARS]
    acs = pd.concat(acs, ignore_index=True)
    acs.insert(0, "GEOID", acs["state"] + acs["county"] + acs["tract"] + acs["block group"])
    acs = acs[["GEOID"] + ACS_VARS]

    # Every block's population summed must equal the state total the API reports
    state_total = int(census_get(s, API_PL, ["P1_001N"], f"state:{fips}", None, key)["P1_001N"].iloc[0])
    block_total = pl["P1_001N"].astype(int).sum()
    assert block_total == state_total, f"blocks sum to {block_total}, state total is {state_total}"
    # The ACS must cover exactly the block groups in the TIGER file
    bg = gpd.read_file(out / f"tl_2020_{fips}_bg.zip", columns=["GEOID"], ignore_geometry=True)["GEOID"]
    missing, extra = set(bg) - set(acs["GEOID"]), set(acs["GEOID"]) - set(bg)
    assert not missing and not extra, f"ACS block groups differ from TIGER: {len(missing)} missing, {len(extra)} extra"

    pl.to_csv(out / "pl2020_blocks.csv", index=False)
    acs.to_csv(out / f"acs{year}_bg.csv", index=False)
    print(f"  pl2020_blocks.csv: {len(pl)} blocks, population {block_total} (matches state total)")
    print(f"  acs{year}_bg.csv: {len(acs)} block groups (matches TIGER)")

    download_2010_era_plan(cfg, pl["GEOID"])
    download_2010_block_elections(cfg)
