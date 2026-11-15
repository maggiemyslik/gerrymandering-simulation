# Builds a fake 30 x 30 grid "state" in exactly the format stages 02 to 05 will produce
# (see README, "data contract"), so stages 06 to 09 and their checks can be run and
# verified before any real data exists. Called by run_synthetic_test.py.

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from gerrychain import Graph
from shapely.geometry import box

from common import RACE_GROUPS, paths


def run(cfg):
    p = paths(cfg)
    p["units"].parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(390)
    side = 30
    n = side * side

    # Grid coordinates; idx runs row by row
    row, col = np.divmod(np.arange(n), side)
    dist = np.hypot(row - 10, col - 12) / side   # distance from a "city" centre

    units = pd.DataFrame({"idx": np.arange(n), "unit_id": [f"U{i:04d}" for i in range(n)]})
    units["TOTPOP"] = rng.integers(900, 1100, n)
    units["COUNTY"] = (row // 6) * 5 + col // 6   # 25 square counties of 6 x 6 units

    # Voting-age population split into the five groups, more diverse near the city
    vap = np.round(units["TOTPOP"] * 0.75)
    weights = np.column_stack([0.3 - 0.2 * dist, 0.4 + 0.5 * dist, 0.15 - 0.1 * dist,
                               np.full(n, 0.1), np.full(n, 0.05)])
    weights = np.clip(weights + rng.normal(0, 0.03, weights.shape), 0.01, None)
    weights = weights / weights.sum(axis=1, keepdims=True)
    for j, g in enumerate(RACE_GROUPS):
        units[g] = np.round(vap * weights[:, j])

    # Economics: richer and more educated towards the city, a few suppressed incomes
    units["LOG_MEDINC"] = np.log(55000 * (1.6 - dist) * np.exp(rng.normal(0, 0.15, n)))
    units["DEGREE_SHARE"] = np.clip(0.45 - 0.4 * dist + rng.normal(0, 0.05, n), 0.02, 0.9)
    units.loc[rng.choice(n, 5, replace=False), "LOG_MEDINC"] = np.nan

    # Votes: Democratic near the city, a small year and race swing, two units with no votes
    base = 1 / (1 + np.exp(-(0.35 - dist) * 8))
    for year, races in cfg["elections"].items():
        for j, race in enumerate(races):
            share = np.clip(base + 0.02 * (year - 2024) / 2 + 0.01 * j + rng.normal(0, 0.05, n), 0.02, 0.98)
            turnout = np.round(units["TOTPOP"] * 0.4)
            units[f"{year}_{race}_D"] = np.round(turnout * share)
            units[f"{year}_{race}_R"] = turnout - units[f"{year}_{race}_D"]
            units.loc[[0, 1], [f"{year}_{race}_D", f"{year}_{race}_R"]] = 0
    units.to_parquet(p["units"], index=False)

    # Geometry: unit squares
    geo = gpd.GeoDataFrame(units[["unit_id", "idx"]], geometry=[box(c, -r, c + 1, -r + 1) for r, c in zip(row, col)])
    geo.to_parquet(p["units_geo"], index=False)

    # Enacted maps: vertical stripes (2021) and horizontal stripes (2025), labels 0..k-1
    k = cfg["n_districts"]
    enacted = units[["idx", "unit_id"]].copy()
    enacted["plan_2021"] = col * k // side
    enacted["plan_2025"] = row * k // side
    enacted.to_parquet(p["enacted"], index=False)

    # Dual graph with the node attributes stage 06 needs: idx, TOTPOP, COUNTY
    g = nx.convert_node_labels_to_integers(nx.grid_2d_graph(side, side), ordering="sorted")
    for i in g.nodes:
        g.nodes[i]["idx"] = i
        g.nodes[i]["TOTPOP"] = int(units.at[i, "TOTPOP"])
        g.nodes[i]["COUNTY"] = int(units.at[i, "COUNTY"])
    Graph.from_networkx(g).to_json(str(p["graph"]))
    print("synthetic state written to", p["units"].parent)
