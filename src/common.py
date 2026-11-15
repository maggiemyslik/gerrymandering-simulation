# Shared helpers for every stage. Numbered scripts cannot be imported as modules,
# so anything used by more than one script lives here.

import json
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

# Voting-age population groups for racial homogeneity (spec section 6, "groups used for race",
# default a: Hispanic, non-Hispanic white, Black, Asian, other, on voting-age population).
RACE_GROUPS = ["VAP_HISP", "VAP_NHWHITE", "VAP_NHBLACK", "VAP_NHASIAN", "VAP_OTHER"]

# Every district property that gets recentred. V, S, L, H change with each year's votes;
# R, E_INC, E_DEG come from 2020 census and one ACS vintage, so they are fixed over time.
PARTISAN_MEASURES = ["V", "S", "L", "H"]
DEMOGRAPHIC_MEASURES = ["R", "E_INC", "E_DEG"]


def load_config(state):
    # One config file per state drives every stage: config/{state}.py, which defines a
    # dictionary called config. Loaded by file path because config/ sits outside src/.
    spec = spec_from_file_location(f"config_{state}", CONFIG / f"{state}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.config


def run_steps(cfg, steps):
    # Runs stage and check modules in order for one state. Each module exposes run(cfg);
    # a failed check raises an error, which stops everything after it.
    for step in steps:
        print(f"\n== {cfg['name']}: {step}", flush=True)
        import_module(step).run(cfg)
    print(f"\n== {cfg['name']}: all steps finished", flush=True)


def years(cfg):
    # Election years with at least one race listed, in order. A year with an empty race
    # list (results not yet joined) is skipped by every stage.
    return sorted(y for y, races in cfg["elections"].items() if races)


def scoring_year(cfg):
    # Single-year figures and the chain diagnostics use the latest year with results.
    return years(cfg)[-1]


def paths(cfg):
    s = cfg["name"]
    return {
        "units": PROCESSED / f"{s}_units.parquet",           # unit attributes, one row per unit, ordered by idx
        "units_geo": PROCESSED / f"{s}_units_geo.parquet",   # unit_id, idx, geometry (for maps)
        "graph": PROCESSED / f"{s}_graph.json",              # dual graph, networkx adjacency JSON
        "enacted": PROCESSED / f"{s}_enacted.parquet",       # idx, unit_id, plan_2010, plan_2021, plan_2025
        "ensemble_dir": PROCESSED / f"{s}_ensemble",         # one chain_{seed}.npz per chain
        "ens_district": PROCESSED / f"{s}_ensemble_district.parquet",
        "ens_district_demo": PROCESSED / f"{s}_ensemble_district_demo.parquet",
        "ens_plan": PROCESSED / f"{s}_ensemble_plan.parquet",
        "enacted_district": PROCESSED / f"{s}_enacted_district.parquet",
        "enacted_district_demo": PROCESSED / f"{s}_enacted_district_demo.parquet",
        "enacted_plan": PROCESSED / f"{s}_enacted_plan.parquet",
        "recentred": PROCESSED / f"{s}_recentred.parquet",
        "pct_by_chain": PROCESSED / f"{s}_percentiles_by_chain.parquet",
    }


def load_units(cfg):
    units = pd.read_parquet(paths(cfg)["units"]).sort_values("idx").reset_index(drop=True)
    # idx must run 0..n-1 so it can index numpy arrays directly
    assert (units["idx"].to_numpy() == np.arange(len(units))).all(), "units idx is not 0..n-1"
    return units


def load_enacted(cfg):
    return pd.read_parquet(paths(cfg)["enacted"]).sort_values("idx").reset_index(drop=True)


def load_graph_nx(cfg):
    # Plain networkx copy of the dual graph, for checks and cut-edge counts.
    # GerryChain 1.0 renumbers nodes internally, so every node carries idx (its row in the
    # units table) and all arrays are keyed on idx, never on graph node ids.
    data = json.loads(paths(cfg)["graph"].read_text())
    return nx.readwrite.json_graph.adjacency_graph(data)


def edge_index(g):
    # Two arrays of unit idx, one entry per graph edge
    u = np.array([g.nodes[a]["idx"] for a, b in g.edges])
    v = np.array([g.nodes[b]["idx"] for a, b in g.edges])
    return u, v


def load_plans(cfg):
    # Stack every chain's retained plans into one (units x plans) array, plus the chain
    # (seed) and draw number of each column.
    files = sorted(paths(cfg)["ensemble_dir"].glob("chain_*.npz"))
    parts = [np.load(f) for f in files]
    plans = np.concatenate([p["plans"] for p in parts], axis=1)
    chain = np.concatenate([np.full(p["plans"].shape[1], int(p["seed"])) for p in parts])
    draw = np.concatenate([p["steps"] for p in parts])
    return plans, chain, draw


def group_sum(labels, weights, k):
    # labels: (units x B) district labels for B plans; weights: (units,) or (units x B).
    # Returns (B x k) district sums. Each plan's labels are offset by k * plan so one
    # bincount call covers the whole batch.
    n, b = labels.shape
    offset = labels.astype(np.int64) + k * np.arange(b)[None, :]
    w = np.broadcast_to(weights[:, None] if weights.ndim == 1 else weights, (n, b))
    return np.bincount(offset.ravel(), weights=w.ravel(), minlength=k * b).reshape(b, k)


def weighted_sd(labels, x, w, k):
    # Population-weighted standard deviation of x within each district (spec section 6).
    # Units where x is missing get zero weight. Variance as mean of x squared minus squared mean;
    # tiny negative values from floating point are clipped to 0 before the square root.
    ok = ~np.isnan(x)
    w = np.where(ok, w, 0.0)
    x = np.where(ok, x, 0.0)
    sw = group_sum(labels, w, k)
    m1 = group_sum(labels, w * x, k) / sw
    m2 = group_sum(labels, w * x * x, k) / sw
    return np.sqrt(np.clip(m2 - m1 ** 2, 0, None))


def unit_shares(units, cfg, year):
    # Each unit's Democratic two-party share in each race of that year: (units x races).
    # A unit with no two-party votes in a race (for example an empty VTD) gets NaN for it.
    races = cfg["elections"][year]
    d = np.column_stack([units[f"{year}_{r}_D"].to_numpy(float) for r in races])
    r = np.column_stack([units[f"{year}_{r}_R"].to_numpy(float) for r in races])
    tot = d + r
    return d, r, np.divide(d, tot, out=np.full_like(tot, np.nan), where=tot > 0)


def score_partisan(labels, units, cfg, year, k):
    # District partisan properties for a batch of plans, each (B x k):
    #   V: composite Democratic two-party share. Per race, district D votes / (D + R votes);
    #      then the equal-weighted mean across the year's races (spec section 3, default c).
    #   S: safety, |V - 0.5| (spec section 6).
    #   L: signed lean towards the party that drew the 2025 map (spec section 7, default: compute both).
    #   H: partisan homogeneity, population-weighted SD of unit composite shares (spec section 6, default a).
    # k is passed in because the 2010-era maps have a different district count (README, open questions).
    d, r, share = unit_shares(units, cfg, year)
    v_races = [group_sum(labels, d[:, j], k) / group_sum(labels, d[:, j] + r[:, j], k)
               for j in range(d.shape[1])]
    V = np.mean(v_races, axis=0)
    S = np.abs(V - 0.5)
    L = {"D": 1, "R": -1}[cfg["mapmaker_party"]] * (V - 0.5)
    # Unit composite: mean over the races where the unit has two-party votes; a unit with
    # none in any race has NaN and so zero weight in H.
    n_ok = (~np.isnan(share)).sum(axis=1)
    unit_v = np.divide(np.nansum(share, axis=1), n_ok, out=np.full(len(units), np.nan), where=n_ok > 0)
    H = weighted_sd(labels, unit_v, units["TOTPOP"].to_numpy(float), k)
    return {"V": V, "S": S, "L": L, "H": H}


def score_demographic(labels, units, k):
    # District demographic properties for a batch of plans, each (B x k):
    #   R: racial homogeneity, Herfindahl index of voting-age population group shares
    #      (spec section 6, "racial homogeneity", default a: composition).
    #   E_INC: population-weighted SD of log median household income across units.
    #   E_DEG: population-weighted SD of the share of adults with a bachelor's degree or higher.
    #   (spec section 6, "economic measure", default c: compute both.)
    groups = np.stack([group_sum(labels, units[g].to_numpy(float), k) for g in RACE_GROUPS])
    R = ((groups / groups.sum(axis=0)) ** 2).sum(axis=0)
    pop = units["TOTPOP"].to_numpy(float)
    E_INC = weighted_sd(labels, units["LOG_MEDINC"].to_numpy(float), pop, k)
    E_DEG = weighted_sd(labels, units["DEGREE_SHARE"].to_numpy(float), pop, k)
    return {"R": R, "E_INC": E_INC, "E_DEG": E_DEG}


def score_plan_level(V, cfg):
    # Plan-level fairness metrics from district composite shares V (B x k), spec section 6.
    # With a composite there is no single vote total, so both use the equal-turnout forms:
    #   efficiency gap = (Democratic seat share - 0.5) - 2 x (mean district V - 0.5)
    #   mean-median    = median district V - mean district V
    # Both are signed so that positive means the plan favours Democrats.
    k = V.shape[1]
    seats_d = (V > 0.5).sum(axis=1)
    return {
        "seats_D": seats_d,
        "competitive": (np.abs(V - 0.5) < cfg["competitive_threshold"]).sum(axis=1),
        "efficiency_gap": (seats_d / k - 0.5) - 2 * (V.mean(axis=1) - 0.5),
        "mean_median": np.median(V, axis=1) - V.mean(axis=1),
    }


def cut_edges(labels, u, v):
    # Number of graph edges whose two units sit in different districts, per plan
    return (labels[u] != labels[v]).sum(axis=0)


def batches(n, size):
    # Plan columns are scored in batches so memory stays small on a laptop
    return [slice(i, min(i + size, n)) for i in range(0, n, size)]
