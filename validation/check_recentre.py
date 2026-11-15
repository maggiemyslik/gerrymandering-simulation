# Check after stage 08 (spec section 9): X equals mu plus Z for every unit, year and measure,
# and unit-level percentiles are stable across independent chains (each chain's percentiles
# against the pooled ones; threshold in config validation.percentile_chain_mad_max).

import numpy as np
import pandas as pd

from common import paths


def run(cfg):
    name = cfg["name"]
    p = paths(cfg)
    rec = pd.read_parquet(p["recentred"])
    assert np.allclose(rec["X"], rec["mu"] + rec["Z"], rtol=0, atol=1e-12), f"{name}: X != mu + Z"
    assert rec[["X", "mu", "Z", "p"]].notna().all().all(), f"{name}: missing values in recentred table"
    print(f"PASS {name}: X = mu + Z for all {len(rec)} unit-year-measure rows")

    chains = pd.read_parquet(p["pct_by_chain"]).merge(
        rec[["unit_id", "year", "measure", "p"]], on=["unit_id", "year", "measure"], suffixes=("_chain", ""))
    chains["gap"] = (chains["p_chain"] - chains["p"]).abs()
    summary = chains.groupby(["year", "measure"])["gap"].agg(["mean", "max"])
    print(summary.round(3).to_string())
    limit = cfg["validation"]["percentile_chain_mad_max"]
    assert (summary["mean"] < limit).all(), \
        f"{name}: percentiles move more than {limit} between chains; more plans needed (spec section 5)"
    print(f"PASS {name}: mean percentile gap between chains below {limit} for every year and measure")
