# Fake state for run_synthetic_test.py: a 30 x 30 grid of units built by
# validation/make_synthetic_state.py. Same keys as the real configs.
config = {
    "name": "synthetic",
    "fips": "99",
    "n_districts": 6,
    "mapmaker_party": "R",
    "unit_type": "grid",

    "elections": {
        2022: ["PRES", "SEN"],
        2024: ["PRES", "SEN", "GOV"],
        2026: ["SEN", "GOV"],
    },

    "map_in_force": {
        2022: "2021",
        2024: "2021",
        2026: "2025",
    },

    # District count of each enacted map. The 2010-era maps were drawn for the 2010 apportionment,
    # so they have a different count from the 2020-geography ensemble (README, open questions).
    "map_districts": {
        "2021": 6,
        "2025": 6,
    },

    # Census pulls used by 01_download.py.
    "acs_year": 2023,

    "ensemble": {
        "pop_tolerance": 0.01,
        "county_surcharge": 0.2,
        "seeds": [1, 2, 3],
        "steps": 1500,
        "burn_in": 300,
        "thin": 4,  # 300 plans per chain, small so the test runs in about a minute
    },

    "competitive_threshold": 0.05,

    "validation": {
        "rhat_max": 1.05,
        "percentile_chain_mad_max": 0.05,
        "n_score_checks": 20,
    },
}
