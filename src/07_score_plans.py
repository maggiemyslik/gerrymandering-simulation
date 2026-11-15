# Stage 07: score every stored ensemble plan and every enacted map (spec section 6).
# Called by run_{state}.py.
# Scoring runs over stored plans, so adding a measure costs minutes, not new chains.
#
# Outputs, per state:
#   ensemble_district       plan, chain, year, district, V, S, L, H
#   ensemble_district_demo  plan, chain, district, R, E_INC, E_DEG (no year: 2020 census and one ACS vintage)
#   ensemble_plan           plan, chain, draw, year, seats_D, competitive, efficiency_gap, mean_median, cut_edges
#   enacted_*               the same, with map ("2010", "2021", "2025") in place of plan and chain.
# Every enacted map is scored under every year's votes, not only the years it was in force,
# so maps can be compared on the same voters; 08 picks the map in force for recentring.
# Definitions of V, S, L, H, R, E_INC, E_DEG and the fairness metrics are in common.py.

import numpy as np
import pandas as pd

from common import (DEMOGRAPHIC_MEASURES, PARTISAN_MEASURES, batches, cut_edges, edge_index,
                    load_enacted, load_graph_nx, load_plans, load_units, paths,
                    score_demographic, score_partisan, score_plan_level, years)


def long_district(scores, measures, ids, k):
    # (B x k) arrays -> long table, one row per plan and district
    out = pd.DataFrame({"plan": np.repeat(ids, k), "district": np.tile(np.arange(k), len(ids))})
    for m in measures:
        out[m] = scores[m].ravel()
    return out


def run(cfg):
    p = paths(cfg)
    units = load_units(cfg)
    u, v = edge_index(load_graph_nx(cfg))
    k = cfg["n_districts"]

    # Ensemble plans
    plans, chain, draw = load_plans(cfg)
    plan_id = np.arange(plans.shape[1])
    district, demo, plan_level = [], [], []
    for b in batches(plans.shape[1], 500):
        labels = plans[:, b]
        demo.append(long_district(score_demographic(labels, units, k), DEMOGRAPHIC_MEASURES, plan_id[b], k))
        n_cut = cut_edges(labels, u, v)
        for year in years(cfg):
            sc = score_partisan(labels, units, cfg, year, k)
            d = long_district(sc, PARTISAN_MEASURES, plan_id[b], k)
            d.insert(1, "year", year)
            district.append(d)
            pl = pd.DataFrame({"plan": plan_id[b], "year": year, **score_plan_level(sc["V"], cfg),
                               "cut_edges": n_cut})
            plan_level.append(pl)
        print(f"{cfg['name']}: scored plans {b.start} to {b.stop - 1}", flush=True)

    meta = pd.DataFrame({"plan": plan_id, "chain": chain, "draw": draw})
    pd.concat(district).merge(meta[["plan", "chain"]], on="plan").to_parquet(p["ens_district"], index=False)
    pd.concat(demo).merge(meta[["plan", "chain"]], on="plan").to_parquet(p["ens_district_demo"], index=False)
    pd.concat(plan_level).merge(meta, on="plan").to_parquet(p["ens_plan"], index=False)

    # Enacted maps, each with its own district count
    enacted = load_enacted(cfg)
    district, demo, plan_level = [], [], []
    for m, km in cfg["map_districts"].items():
        labels = enacted[[f"plan_{m}"]].to_numpy()
        dm = long_district(score_demographic(labels, units, km), DEMOGRAPHIC_MEASURES, [m], km)
        demo.append(dm.rename(columns={"plan": "map"}))
        for year in years(cfg):
            sc = score_partisan(labels, units, cfg, year, km)
            d = long_district(sc, PARTISAN_MEASURES, [m], km).rename(columns={"plan": "map"})
            d.insert(1, "year", year)
            district.append(d)
            plan_level.append(pd.DataFrame({"map": [m], "year": year, **score_plan_level(sc["V"], cfg),
                                            "cut_edges": cut_edges(labels, u, v)}))
    pd.concat(district).to_parquet(p["enacted_district"], index=False)
    pd.concat(demo).to_parquet(p["enacted_district_demo"], index=False)
    pd.concat(plan_level).to_parquet(p["enacted_plan"], index=False)
    print(f"{cfg['name']}: scores written", flush=True)
