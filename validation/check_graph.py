# Check after stage 05: the dual graph is connected, its idx matches the units table,
# and every enacted district is contiguous on the graph (spec section 9).

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from common import edge_index, load_enacted, load_graph_nx, load_units


def run(cfg):
    name = cfg["name"]
    units = load_units(cfg)
    g = load_graph_nx(cfg)
    n = len(units)

    idx = sorted(g.nodes[a]["idx"] for a in g.nodes)
    assert idx == list(range(n)), f"{name}: graph idx does not match units 0..{n - 1}"
    pop_graph = sum(g.nodes[a]["TOTPOP"] for a in g.nodes)
    assert pop_graph == units["TOTPOP"].sum(), f"{name}: graph population differs from units table"

    u, v = edge_index(g)
    adj = sp.coo_matrix((np.ones(len(u)), (u, v)), shape=(n, n))
    n_comp, _ = connected_components(adj, directed=False)
    assert n_comp == 1, f"{name}: graph has {n_comp} components; patch islands in stage 05"
    print(f"PASS {name}: graph connected, {n} units, {len(u)} edges")

    enacted = load_enacted(cfg)
    for m, k in cfg["map_districts"].items():
        labels = enacted[f"plan_{m}"].to_numpy()
        assert set(np.unique(labels)) == set(range(k)), f"{name} map {m}: labels are not 0..{k - 1}"
        # Keep only edges inside a district; contiguous means one component per district
        same = labels[u] == labels[v]
        inner = sp.coo_matrix((np.ones(same.sum()), (u[same], v[same])), shape=(n, n))
        n_comp, _ = connected_components(inner, directed=False)
        assert n_comp == k, f"{name} map {m}: {n_comp - k} extra pieces, some district is not contiguous"
        print(f"PASS {name} map {m}: all {k} districts contiguous")
