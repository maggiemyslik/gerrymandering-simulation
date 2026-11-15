# Stage 01: downloads everything that can be fetched by script, all from the US Census Bureau.
# Called by download_{state}.py.
# Every other source needs a login, an extract request or a portal click; those are downloaded
# by hand following the README into the same data/raw/{state}/ folders.
#
# Per state, into data/raw/{state}/census/:
#   tl_2020_{fips}_tabblock20.zip   TIGER/Line 2020 census blocks: geometry and total population (POP20)
#   tl_2020_{fips}_bg.zip           TIGER/Line 2020 block groups: geometry
#
# The Census API is not used: it rejects valid keys from outside the US. Total population from
# the block file is all build steps 1 to 4 need. Voting-age population by race (PL 94-171) and
# ACS income and education are added from Census bulk files at build steps 5 and 6.

import requests

from common import RAW

TIGER = "https://www2.census.gov/geo/tiger/TIGER2020"


def download(url, dest):
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"  {dest.name}: {len(r.content) / 1e6:.1f} MB")


def run(cfg):
    fips = cfg["fips"]
    out = RAW / cfg["name"] / "census"
    out.mkdir(parents=True, exist_ok=True)
    print(cfg["name"])
    download(f"{TIGER}/TABBLOCK20/tl_2020_{fips}_tabblock20.zip", out / f"tl_2020_{fips}_tabblock20.zip")
    download(f"{TIGER}/BG/tl_2020_{fips}_bg.zip", out / f"tl_2020_{fips}_bg.zip")