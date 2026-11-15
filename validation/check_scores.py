# Check after stage 07 (spec section 9): district scores recomputed from scratch for a random
# sample of plans, and for every enacted map, match the stored scores. The recomputation uses
# pandas groupby and a deviation-based variance formula, deliberately independent of the
# vectorised bincount code in common.py.

import numpy as np
import pandas as pd

from common import (RACE_GROUPS, load_enacted, load_plans, load_units,
                    paths, years)


def wsd(df, col):
    # Population-weighted SD within each district, skipping missing values
    d = df.dropna(subset=[col])
    w = d["TOTPOP"]
    mean = (w * d[col]).groupby(d["district"]).sum() / w.groupby(d["district"]).sum()
    dev = (d[col] - d["district"].map(mean)) ** 2
    return np.sqrt((w * dev).groupby(d["district"]).sum() / w.groupby(d["district"]).sum())


def from_scratch(units, labels, cfg, year):
    df = units.assign(district=labels)
    races = cfg["elections"][year]
    g = df.groupby("district")
    V = sum(g[f"{year}_{r}_D"].sum() / (g[f"{year}_{r}_D"].sum() + g[f"{year}_{r}_R"].sum())
            for r in races) / len(races)
    # Unit composite share: mean over the races where the unit has two-party votes
    shares = pd.DataFrame({r: df[f"{year}_{r}_D"] / (df[f"{year}_{r}_D"] + df[f"{year}_{r}_R"])
                           for r in races}).replace([np.inf, -np.inf], np.nan)
    df["unit_v"] = shares.mean(axis=1, skipna=True)
    vap = g[RACE_GROUPS].sum()
    sign = 1 if cfg["mapmaker_party"] == "D" else -1
    return pd.DataFrame({"V": V, "S": (V - 0.5).abs(), "L": sign * (V - 0.5), "H": wsd(df, "unit_v"),
                         "R": (vap.div(vap.sum(axis=1), axis=0) ** 2).sum(axis=1),
                         "E_INC": wsd(df, "LOG_MEDINC"), "E_DEG": wsd(df, "DEGREE_SHARE")})


def run(cfg):
    name = cfg["name"]
    p = paths(cfg)
    units = load_units(cfg)
    plans, _, _ = load_plans(cfg)
    ens = pd.read_parquet(p["ens_district"]).set_index(["plan", "year", "district"]).sort_index()
    ens_demo = pd.read_parquet(p["ens_district_demo"]).set_index(["plan", "district"]).sort_index()
    enc = pd.read_parquet(p["enacted_district"]).set_index(["map", "year", "district"]).sort_index()
    enc_demo = pd.read_parquet(p["enacted_district_demo"]).set_index(["map", "district"]).sort_index()

    rng = np.random.default_rng(0)
    sample = rng.choice(plans.shape[1], cfg["validation"]["n_score_checks"], replace=False)
    worst = 0.0
    for year in years(cfg):
        cases = [(plans[:, j], ens.loc[(j, year)], ens_demo.loc[j]) for j in sample]
        cases += [(load_enacted(cfg)[f"plan_{m}"].to_numpy(), enc.loc[(m, year)], enc_demo.loc[m])
                  for m in cfg["map_districts"]]
        for labels, stored, stored_demo in cases:
            fresh = from_scratch(units, labels, cfg, year)
            stored_all = stored[["V", "S", "L", "H"]].join(stored_demo[["R", "E_INC", "E_DEG"]])
            gap = np.abs(fresh.sort_index().to_numpy() - stored_all.sort_index().to_numpy()).max()
            worst = max(worst, gap)
    assert worst < 1e-8, f"{name}: stored scores differ from recomputed ones by up to {worst:.2e}"
    print(f"PASS {name}: {len(sample)} ensemble plans and every enacted map match, max gap {worst:.1e}")
