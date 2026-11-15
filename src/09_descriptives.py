# Stage 09: first descriptives (spec section 8). Three questions before any outcome exists:
# how far the enacted maps sit from neutral, whether safety and homogeneity are separable,
# and how much of each is geography (mu) versus mapmaker (Z).
#
# Single-year figures use the latest year with results (common.scoring_year) and compare the
# 2021 and 2025 maps, both scored with those same votes, so differences are map differences only.
# Sorted-district box plots sort each measure by its own value within every plan (the standard
# form), rather than by Democratic share.
# Averages over units are population-weighted, since units differ in size.
# The treatment-dose figures need 2026 results. The Texas versus California comparison is a
# separate step, added once both states have run.
# Called by run_{state}.py.

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from common import FIGURES, TABLES, load_units, paths, scoring_year, years  # noqa: E402

MAPS = {"2021": "tab:blue", "2025": "tab:red"}   # the two maps compared in single-year figures
LABELS = {"V": "Democratic two-party share", "S": "safety |V - 0.5|", "L": "lean towards mapmaker party",
          "H": "partisan homogeneity (SD of unit shares)", "R": "racial homogeneity (Herfindahl)",
          "E_INC": "income spread (SD of log median income)", "E_DEG": "education spread (SD of degree share)"}


def save(fig, name):
    fig.savefig(FIGURES / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def sorted_box(ax, ens, enc, measure, k):
    # Ensemble boxes per rank, enacted maps as dots at the same ranks
    arr = np.sort(ens.sort_values(["plan", "district"])[measure].to_numpy().reshape(-1, k), axis=1)
    ax.boxplot(arr, positions=range(1, k + 1), widths=0.6, showfliers=False)
    for m, colour in MAPS.items():
        vals = np.sort(enc.loc[enc["map"] == m, measure].to_numpy())
        ax.scatter(range(1, k + 1), vals, color=colour, s=14, zorder=3, label=f"enacted {m}")
    ax.set_xticks(range(1, k + 1, max(1, k // 10)))
    ax.set_xlabel("districts, ranked within each plan")
    ax.set_ylabel(LABELS[measure])


def run(cfg):
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    name, k, year = cfg["name"], cfg["n_districts"], scoring_year(cfg)
    p = paths(cfg)
    ens_d = pd.read_parquet(p["ens_district"])
    ens_d = ens_d[ens_d["year"] == year]
    ens_demo = pd.read_parquet(p["ens_district_demo"])
    ens_plan = pd.read_parquet(p["ens_plan"])
    ens_plan = ens_plan[ens_plan["year"] == year]
    enc_d = pd.read_parquet(p["enacted_district"])
    enc_d = enc_d[(enc_d["year"] == year) & enc_d["map"].isin(MAPS)]
    enc_demo = pd.read_parquet(p["enacted_district_demo"])
    enc_plan = pd.read_parquet(p["enacted_plan"])
    enc_plan = enc_plan[(enc_plan["year"] == year) & enc_plan["map"].isin(MAPS)]
    ens_all = ens_d.merge(ens_demo, on=["plan", "chain", "district"])
    enc_all = enc_d.merge(enc_demo, on=["map", "district"])

    # 1. How unusual are the enacted maps? Seats won across the ensemble
    fig, ax = plt.subplots(figsize=(7, 4))
    seats = ens_plan["seats_D"]
    ax.hist(seats, bins=np.arange(seats.min() - 0.5, seats.max() + 1.5), color="grey", alpha=0.7)
    for _, r in enc_plan.iterrows():
        ax.axvline(r["seats_D"], color=MAPS[r["map"]], lw=2, label=f"enacted {r['map']}")
    ax.set(xlabel=f"Democratic seats ({year} votes)", ylabel="ensemble plans", title=f"{name}: seats")
    ax.legend()
    save(fig, f"seats_hist_{name}.png")

    # 2. Where does the departure happen, and did the redraws pack by making districts alike
    # or just lopsided? Sorted-district box plots for V, H and R
    for measure in ["V", "H", "R"]:
        fig, ax = plt.subplots(figsize=(10, 4))
        sorted_box(ax, ens_all, enc_all, measure, k)
        ax.legend()
        ax.set_title(f"{name}: {LABELS[measure]} ({year} votes)")
        save(fig, f"sorted_box_{measure}_{name}.png")

    # 3. Are safety and homogeneity separable? If S and H are almost perfectly correlated,
    # the safety-homogeneity tension cannot be tested and the RQ must change
    fig, ax = plt.subplots(figsize=(6, 5))
    hb = ax.hexbin(ens_d["S"], ens_d["H"], gridsize=40, mincnt=1, cmap="Greys")
    for m, colour in MAPS.items():
        e = enc_d[enc_d["map"] == m]
        ax.scatter(e["S"], e["H"], color=colour, s=16, label=f"enacted {m}")
    ax.set(xlabel=LABELS["S"], ylabel=LABELS["H"], title=f"{name}: safety vs homogeneity ({year})")
    fig.colorbar(hb, label="ensemble districts")
    ax.legend()
    save(fig, f"safety_vs_homogeneity_{name}.png")

    # 4. Correlations across ensemble districts: safety vs homogeneity, and whether demographic
    # and partisan homogeneity coincide
    ens_all[["S", "H", "R", "E_INC", "E_DEG"]].corr().round(3).to_csv(TABLES / f"district_correlations_{name}.csv")

    # 5. Do the "neutral" metrics agree? Enacted fairness metrics against their ensemble distributions
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    rows = []
    for ax, metric in zip(axes, ["efficiency_gap", "mean_median"]):
        ax.hist(ens_plan[metric], bins=40, color="grey", alpha=0.7)
        for _, r in enc_plan.iterrows():
            ax.axvline(r[metric], color=MAPS[r["map"]], lw=2, label=f"enacted {r['map']}")
        ax.set(xlabel=f"{metric} (positive favours Democrats)", ylabel="ensemble plans")
    axes[0].legend()
    fig.suptitle(f"{name}: fairness metrics ({year} votes)")
    save(fig, f"fairness_{name}.png")
    for _, r in enc_plan.iterrows():
        for metric in ["seats_D", "competitive", "efficiency_gap", "mean_median", "cut_edges"]:
            rows.append({"map": r["map"], "metric": metric, "enacted": r[metric],
                         "ensemble_mean": ens_plan[metric].mean(),
                         "ensemble_percentile": (ens_plan[metric] < r[metric]).mean()
                         + 0.5 * (ens_plan[metric] == r[metric]).mean()})
    pd.DataFrame(rows).to_csv(TABLES / f"enacted_vs_ensemble_{name}.csv", index=False)

    # 6. Geography or mapmaker? Population-weighted mean mu and mean |Z| by year (Chen and Rodden)
    rec = pd.read_parquet(p["recentred"]).merge(load_units(cfg)[["unit_id", "TOTPOP"]], on="unit_id")
    rec["absZ"] = rec["Z"].abs()
    trend = rec.groupby(["measure", "year"]).apply(
        lambda d: pd.Series({"mean_mu": np.average(d["mu"], weights=d["TOTPOP"]),
                             "mean_abs_Z": np.average(d["absZ"], weights=d["TOTPOP"])}),
        include_groups=False).reset_index()
    trend.to_csv(TABLES / f"geography_vs_mapmaker_{name}.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, measure in zip(axes, ["H", "S"]):
        t = trend[trend["measure"] == measure]
        ax.plot(t["year"], t["mean_mu"], marker="o", label="mean mu (geography)")
        ax.plot(t["year"], t["mean_abs_Z"], marker="o", label="mean |Z| (mapmaker)")
        ax.set(xlabel="election year", ylabel=LABELS[measure], xticks=years(cfg))
    axes[0].legend()
    fig.suptitle(f"{name}: geography versus mapmaker")
    save(fig, f"geography_vs_mapmaker_{name}.png")

    # 7. Who was treated? Change in Z from 2024 to 2026, the continuous dose for the DiD
    if {2024, 2026} <= set(years(cfg)):
        geo = gpd.read_parquet(p["units_geo"])
        for measure in ["H", "S"]:
            z = rec[rec["measure"] == measure].pivot(index="unit_id", columns="year", values="Z")
            dose = (z[2026] - z[2024]).rename("dose").reset_index()
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
            lim = dose["dose"].abs().max()
            geo.merge(dose, on="unit_id").plot(column="dose", cmap="RdBu_r", vmin=-lim, vmax=lim,
                                                legend=True, ax=axes[0], linewidth=0)
            axes[0].set_axis_off()
            axes[1].hist(dose["dose"], bins=50, color="grey")
            axes[1].set(xlabel=f"change in Z ({measure}), 2024 to 2026", ylabel="units")
            fig.suptitle(f"{name}: treatment dose, {LABELS[measure]}")
            save(fig, f"dose_{measure}_{name}.png")

    print(f"{name}: descriptives written to outputs/")
