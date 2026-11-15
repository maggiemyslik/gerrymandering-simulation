# California configuration. Every script reads this; nothing state-specific lives in code.
config = {
    "name": "california",
    "fips": "06",
    "n_districts": 52,

    # Party that drew the 2025 map. Orients the signed lean L so that positive = lean towards
    # the mapmaker's party (spec section 7, "signed lean or safety": compute both S and L).
    "mapmaker_party": "D",

    # Base units: 2020 census block groups. Departs from the spec default (Statewide Database
    # precincts) because those precincts are redrawn every election, so they give no fixed layer
    # across 2016 to 2026. Statewide Database votes already sit on 2020 blocks, so block groups
    # receive them by exact aggregation, with no proration.
    "unit_type": "block_group",

    # Statewide races entering each year's partisan composite (spec section 3, default c:
    # the contemporaneous year's statewide races, built as a composite within each year).
    # Every statewide race with both a Democratic and a Republican candidate is included,
    # weighted equally. Race codes become column names {year}_{race}_D and {year}_{race}_R
    # in the units table. Filled in once the raw election files' column headers are known.
    "elections": {
        2022: [],
        2024: [],
    },

    # Which enacted map was in force for each election year (spec, "scope").
    "map_in_force": {
        2016: "2010",
        2018: "2010",
        2020: "2010",
        2022: "2021",
        2024: "2021",
        2026: "2025",
    },

    # District count of each enacted map. The 2010-era maps were drawn for the 2010 apportionment,
    # so they have a different count from the 2020-geography ensemble (README, open questions).
    "map_districts": {
        "2010": 53,
        "2021": 52,
        "2025": 52,
    },

    # Census pulls used by 01_download.py.
    "acs_year": 2023,  # ACS 5-year 2019-2023, published on 2020 block groups

    "ensemble": {
        "pop_tolerance": 0.01,     # spec section 5, default b (1%)
        "county_surcharge": 0.2,   # spec section 5, county splits default b: mild penalty, same in both states
        "seeds": [1, 2, 3, 4, 5],  # 5 chains run in parallel (spec section 5, ensemble size default)
        "steps": 100000,
        "burn_in": 20000,
        "thin": 40,                # (100000 - 20000) / 40 = 2000 plans per chain, 10000 in total
    },

    "competitive_threshold": 0.05,  # spec section 6, default: S below 0.05 for descriptive counts

    "validation": {
        "rhat_max": 1.05,                  # chains treated as converged below this
        "percentile_chain_mad_max": 0.05,  # mean absolute gap between a chain's percentiles and the pooled ones
        "n_score_checks": 20,              # plans re-scored from scratch in check_scores.py
    },
}
