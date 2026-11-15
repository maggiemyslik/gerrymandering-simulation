# Stage 08: split each unit's district property into a geography part and a mapmaker part
# (spec section 7). Called by run_{state}.py. For unit i, year t, property X:
#   X   = property of i's district under the map in force in year t, scored with year t votes
#   mu  = mean of i's district property across all ensemble plans, scored with year t votes
#         (centre: ensemble mean, spec section 7 default a, matching Borusyak and Hull)
#   Z   = X - mu, the recentred treatment
#   p   = share of ensemble plans in which i's district has a LOWER value than under the
#         enacted map (ties count half). One direction for every measure: p near 0 means the
#         enacted value is unusually low, near 1 unusually high. For H a low p means unusually
#         homogeneous; for S a high p means unusually safe.
# Votes used each year: that year's results (spec section 7, default a), so mu moves as voters
# sort. R, E_INC and E_DEG are fixed over time (2020 census, one ACS vintage), so their mu is
# constant and is absorbed by unit fixed effects in a DiD; they still matter cross-sectionally.
#
# Outputs: recentred (unit_id, year, measure, X, mu, Z, p) and percentiles_by_chain
# (unit_id, year, measure, chain, p), the latter for the chain-stability check.

import numpy as np
import pandas as pd

from common import (DEMOGRAPHIC_MEASURES, PARTISAN_MEASURES, batches, load_enacted, load_plans,
                    load_units, paths, years)


def district_array(df, value, n_plans, k):
    # Long (plan, district) table -> (plans x k) array, row = plan id, column = district label
    df = df.sort_values(["plan", "district"])
    return df[value].to_numpy().reshape(n_plans, k)


def run(cfg):
    p = paths(cfg)
    units = load_units(cfg)
    enacted = load_enacted(cfg)
    plans, chain, _ = load_plans(cfg)
    n, n_plans = plans.shape
    k = cfg["n_districts"]
    chains = np.unique(chain)

    ens_d = pd.read_parquet(p["ens_district"])
    ens_demo = pd.read_parquet(p["ens_district_demo"])
    enc_d = pd.read_parquet(p["enacted_district"])
    enc_demo = pd.read_parquet(p["enacted_district_demo"])

    pooled, by_chain = [], []
    for year in years(cfg):
        m = cfg["map_in_force"][year]
        # The ensemble has the 2020 apportionment's district count; recentring a map with a
        # different count against it is not meaningful (README, open questions)
        assert cfg["map_districts"][m] == k, (
            f"{cfg['name']} {year}: map {m} has {cfg['map_districts'][m]} districts, "
            f"ensemble has {k}; see README open questions")
        enacted_labels = enacted[f"plan_{m}"].to_numpy()

        ens_year = ens_d[ens_d["year"] == year]
        enc_year = enc_d[(enc_d["year"] == year) & (enc_d["map"] == m)].sort_values("district")
        enc_map_demo = enc_demo[enc_demo["map"] == m].sort_values("district")

        for measure in PARTISAN_MEASURES + DEMOGRAPHIC_MEASURES:
            ens_src, enc_src = (ens_year, enc_year) if measure in PARTISAN_MEASURES else (ens_demo, enc_map_demo)
            dist_vals = district_array(ens_src, measure, n_plans, k)
            X = enc_src[measure].to_numpy()[enacted_labels]

            # Each unit's value under each ensemble plan, accumulated in batches
            total = np.zeros(n)
            below = {c: np.zeros(n) for c in chains}
            for b in batches(n_plans, 500):
                cols = np.arange(b.start, b.stop)
                vals = dist_vals[cols[None, :], plans[:, b]]          # (units x batch)
                total += vals.sum(axis=1)
                rank = (vals < X[:, None]) + 0.5 * (vals == X[:, None])
                for c in chains:
                    below[c] += rank[:, chain[cols] == c].sum(axis=1)

            mu = total / n_plans
            counts = {c: (chain == c).sum() for c in chains}
            pct = sum(below.values()) / n_plans
            pooled.append(pd.DataFrame({"unit_id": units["unit_id"], "year": year, "measure": measure,
                                        "X": X, "mu": mu, "Z": X - mu, "p": pct}))
            for c in chains:
                by_chain.append(pd.DataFrame({"unit_id": units["unit_id"], "year": year, "measure": measure,
                                              "chain": c, "p": below[c] / counts[c]}))
        print(f"{cfg['name']} {year}: recentred", flush=True)

    pd.concat(pooled).to_parquet(p["recentred"], index=False)
    pd.concat(by_chain).to_parquet(p["pct_by_chain"], index=False)
