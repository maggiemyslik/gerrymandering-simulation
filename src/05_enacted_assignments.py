# Stage 05: puts each enacted map on the units and builds the map graph. Called by run_{state}.py.
#
# Enacted maps (README, choices: units split by an enacted map). Maps assign census blocks to
# districts; the ensemble moves whole units. Each unit goes to the district holding most of its
# population (most of its blocks if it has no population). The number of split units and the
# population placed in a different district from the real map are written to
# outputs/tables/{state}_enacted_splits.csv. District codes become labels 0..k-1 in numeric order.
#
# Map graph (README, choices: neighbours and islands). Units are neighbours if their borders share
# a stretch of line (rook adjacency), measured in the projected coordinate system. Any part of the
# state left unconnected (islands) is linked to the nearest unit in the connected mainland, in the
# same county where possible, as islands are districted with a nearby stretch of coast. Every link
# is written to outputs/tables/{state}_island_links.csv. Node attributes: idx, TOTPOP, COUNTY.

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely
from gerrychain import Graph

from common import RAW, load_units, paths


def read_plan(cfg, spec):
    # Returns block GEOID and district code, both as text, for one enacted map file
    path = RAW / cfg["name"] / "plans" / spec["path"]
    if spec["format"] == "census_baf":
        plan = pd.read_csv(path, sep="|", dtype=str).rename(columns={"BLOCKID": "GEOID", "DISTRICT": "district"})
    elif spec["format"] == "xlsx_no_header":
        plan = pd.read_excel(path, header=None, dtype=str).rename(columns={0: "GEOID", 1: "district"})
    elif spec["format"] == "csv_no_header":
        plan = pd.read_csv(path, header=None, dtype=str).rename(columns={0: "GEOID", 1: "district"})
    # Spreadsheets drop the leading zero of California's state code, so IDs are padded to 15 digits
    plan["GEOID"] = plan["GEOID"].str.strip().str.zfill(15)
    plan["district"] = plan["district"].str.strip()
    assert plan["GEOID"].is_unique, f"{spec['path']}: a block appears twice"
    return plan[["GEOID", "district"]]


def assign_units(cfg, blocks, plan, key):
    blk = blocks.merge(plan, on="GEOID", how="left")
    unassigned = blk["district"].isna()
    not_in_map = blk.loc[unassigned, "P1_001N"].sum()
    blk = blk[~unassigned]
    by = (blk.groupby(["unit_id", "district"]).agg(pop=("P1_001N", "sum"), n=("GEOID", "size"))
          .reset_index().sort_values(["unit_id", "pop", "n"], ascending=[True, False, False]))
    chosen = by.drop_duplicates("unit_id").set_index("unit_id")["district"]
    codes = sorted(chosen.unique(), key=int)
    assert len(codes) == cfg["map_districts"][key], f"map {key}: {len(codes)} districts, config expects {cfg['map_districts'][key]}"
    moved = blk["district"].to_numpy() != blk["unit_id"].map(chosen).to_numpy()
    split = by.groupby("unit_id").size() > 1
    stats = {"map": key, "districts": len(codes), "units_split": int(split.sum()),
             "population_moved": int(blk.loc[moved, "P1_001N"].sum()),
             "share_moved": blk.loc[moved, "P1_001N"].sum() / blocks["P1_001N"].sum(),
             "blocks_not_in_map": int(unassigned.sum()),
             "population_not_in_map": int(not_in_map)}
    return chosen.map({c: i for i, c in enumerate(codes)}), stats


def rook_graph(geo):
    # Candidate pairs from bounding boxes, kept if their borders share a line of positive length
    g = nx.Graph()
    g.add_nodes_from(range(len(geo)))
    geoms = geo.geometry.to_numpy()
    i, j = shapely.STRtree(geoms).query(geoms, predicate="intersects")
    keep = i < j
    i, j = i[keep], j[keep]
    shared = shapely.length(shapely.intersection(shapely.boundary(geoms[i]), shapely.boundary(geoms[j])))
    g.add_edges_from(zip(i[shared > 0], j[shared > 0]))
    return g


def link_islands(g, geo, units):
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    mainland = np.array(sorted(comps[0]))
    links = []
    for comp in comps[1:]:
        comp = np.array(sorted(comp))
        county = units.loc[comp, "COUNTY"].mode().iloc[0]
        same = mainland[units.loc[mainland, "COUNTY"].to_numpy() == county]
        targets = same if len(same) else mainland
        # Nearest pair of units between the island and the chosen part of the mainland
        tree = shapely.STRtree(geo.geometry.to_numpy()[targets])
        src_idx, tgt_pos = tree.query_nearest(geo.geometry.to_numpy()[comp], return_distance=False, all_matches=False)
        dists = shapely.distance(geo.geometry.to_numpy()[comp[src_idx]], geo.geometry.to_numpy()[targets[tgt_pos]])
        best = np.argmin(dists)
        a, b = comp[src_idx[best]], targets[tgt_pos[best]]
        g.add_edge(int(a), int(b))
        links.append({"island_units": len(comp), "island_population": int(units.loc[comp, "TOTPOP"].sum()),
                      "island_unit": units.at[a, "unit_id"], "mainland_unit": units.at[b, "unit_id"],
                      "distance_km": round(float(dists[best]) / 1000, 2), "same_county": bool(len(same))})
    assert nx.is_connected(g), "graph still disconnected after linking islands"
    return pd.DataFrame(links, columns=["island_units", "island_population", "island_unit", "mainland_unit",
                                        "distance_km", "same_county"])


def run(cfg):
    p = paths(cfg)
    units = load_units(cfg)
    blocks = pd.read_csv(RAW / cfg["name"] / "census" / "pl2020_blocks.csv", dtype={"GEOID": str},
                         usecols=["GEOID", "P1_001N"])
    blocks["unit_id"] = blocks["GEOID"].str[:12]

    enacted = units[["idx", "unit_id"]].copy()
    stats = []
    for key, spec in cfg["plan_files"].items():
        labels, s = assign_units(cfg, blocks, read_plan(cfg, spec), key)
        enacted[f"plan_{key}"] = enacted["unit_id"].map(labels)
        assert enacted[f"plan_{key}"].notna().all(), f"map {key}: some units have no blocks in the map"
        enacted[f"plan_{key}"] = enacted[f"plan_{key}"].astype(np.int16)
        stats.append(s)
        print(f"{cfg['name']} map {key}: {s['units_split']} units split, "
              f"{s['population_moved']} people ({s['share_moved']:.3%}) placed in a different district")
    p["enacted_splits"].parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(stats).to_csv(p["enacted_splits"], index=False)
    enacted.to_parquet(p["enacted"], index=False)

    geo = gpd.read_parquet(p["units_geo"]).sort_values("idx").reset_index(drop=True)
    g = rook_graph(geo)
    links = link_islands(g, geo, units)
    links.to_csv(p["island_links"], index=False)
    for i in g.nodes:
        g.nodes[i]["idx"] = int(i)
        g.nodes[i]["TOTPOP"] = int(units.at[i, "TOTPOP"])
        g.nodes[i]["COUNTY"] = int(units.at[i, "COUNTY"])
    Graph.from_networkx(g).to_json(str(p["graph"]))
    print(f"{cfg['name']}: graph with {g.number_of_nodes()} units, {g.number_of_edges()} edges, "
          f"{len(links)} island links")
