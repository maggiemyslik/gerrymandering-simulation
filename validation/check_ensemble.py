# Check after stage 06 (spec section 9): every stored plan is within the population tolerance
# and contiguous; chains have converged (R-hat across chains, effective sample size); and
# trace plots of the summary statistics are written for inspection.
# Summary statistics: cut edges, Democratic seats and competitive districts, the last two
# under the latest year with results. The comparison with ALARM's published ensembles is
# added once the ALARM files are downloaded and their format is known (README).

import arviz as az
import matplotlib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import (FIGURES, batches, cut_edges, edge_index, group_sum, load_graph_nx,
                    load_plans, load_units, score_partisan, score_plan_level,
                    scoring_year)


def run(cfg):
    name = cfg["name"]
    k = cfg["n_districts"]
    units = load_units(cfg)
    plans, chain, draw = load_plans(cfg)
    n, n_plans = plans.shape
    u, v = edge_index(load_graph_nx(cfg))
    pop = units["TOTPOP"].to_numpy(float)
    ideal = pop.sum() / k
    tol = cfg["ensemble"]["pop_tolerance"]

    # Population and contiguity, every plan
    worst = 0.0
    stats = []
    for b in batches(n_plans, 500):
        labels = plans[:, b]
        dev = np.abs(group_sum(labels, pop, k) / ideal - 1).max()
        worst = max(worst, dev)
        for j in range(labels.shape[1]):
            lab = labels[:, j]
            same = lab[u] == lab[v]
            inner = sp.coo_matrix((np.ones(same.sum()), (u[same], v[same])), shape=(n, n))
            assert connected_components(inner, directed=False)[0] == k, \
                f"{name}: plan {b.start + j} has a non-contiguous district"
        V = score_partisan(labels, units, cfg, scoring_year(cfg), k)["V"]
        pl = score_plan_level(V, cfg)
        stats.append(pd.DataFrame({"cut_edges": cut_edges(labels, u, v), "seats_D": pl["seats_D"],
                                   "competitive": pl["competitive"]}))
    assert worst <= tol + 1e-9, f"{name}: a plan is {worst:.4f} off ideal population, tolerance {tol}"
    print(f"PASS {name}: {n_plans} plans, all contiguous, worst population deviation {worst:.4%}")

    # Convergence: chains as rows, draws as columns (every chain keeps the same number of plans)
    stats = pd.concat(stats, ignore_index=True)
    stats["chain"], stats["draw"] = chain, draw
    seeds = np.unique(chain)
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for ax, s in zip(axes, ["cut_edges", "seats_D", "competitive"]):
        arr = np.stack([stats.loc[stats["chain"] == c, s].to_numpy(float) for c in seeds])
        rhat, ess = float(az.rhat(arr)), float(az.ess(arr))
        print(f"{name} {s}: R-hat {rhat:.3f}, effective sample size {ess:.0f}")
        assert rhat < cfg["validation"]["rhat_max"], \
            f"{name} {s}: R-hat {rhat:.3f}; run longer chains or more plans (spec section 5)"
        for c in seeds:
            sub = stats[stats["chain"] == c]
            ax.plot(sub["draw"], sub[s], lw=0.6, label=f"chain {c}")
        ax.set_ylabel(s)
    axes[0].legend(fontsize=7, ncol=len(seeds))
    axes[-1].set_xlabel("chain step")
    fig.suptitle(f"{name}: chain traces")
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"diag_traces_{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"PASS {name}: R-hat below {cfg['validation']['rhat_max']} for every summary statistic")
