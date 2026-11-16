# GV390 ensemble simulation pipeline

Builds neutral ensembles of congressional maps for Texas and California, scores every enacted and simulated map on safety and homogeneity, and recentres each unit's treatment against its ensemble, for elections 2016 to 2026. Everything here is treatment-side and descriptive; no outcome variable is built yet. The design follows the GV390 code specification (1 November 2026); section numbers below refer to it.

## Status

| Stage | Script | Status |
|---|---|---|
| 00 | `src/00_inspect_raw.py` | written, tested on dummy files |
| 01 | `src/01_download.py` | written and run for both states (Census API and Census bulk site) |
| runners | `download_{state}.py`, `run_{state}.py`, `run_synthetic_test.py` | written; the state runners currently contain only the stages that can run on raw data (00), the rest are added as stages 02 to 05 are written |
| 02 to 05 | units, votes onto blocks, votes onto units, enacted maps and graph | California written and tested on mock data (2022 and 2024 votes); Texas, and California 2016 to 2020 votes, written once those files are inspected |
| 06 to 09 | ensemble, scoring, recentring, descriptives | written and verified end to end on the synthetic state |
| checks | `check_graph`, `check_ensemble`, `check_scores`, `check_recentre` | written and verified on the synthetic state |
| checks | `check_units`, `check_crosswalk`, `check_enacted` | written, tested on mock data |

## Repository structure

```
gv390/
  download_texas.py       Census downloads for Texas (run once)
  download_california.py
  run_texas.py            the whole Texas pipeline, every stage followed by its check
  run_california.py
  run_synthetic_test.py   the same stages on a fake state, to test the code
  config/
    texas.py            one config per state: paths, district counts, constraints, elections
    california.py
    synthetic.py        fake grid state for testing stages 06 to 09
  .env                    Census API key (not committed; see setup)
  data/raw/{state}/       downloads, untouched
  data/interim/           cleaned units, crosswalks, joined attributes
  data/processed/         unit graph, plan assignments, scored plans, recentred treatments
  src/
    common.py             shared helpers and all scoring maths
    00_inspect_raw.py     prints the columns and first rows of every raw file
    01_download.py ... 09_descriptives.py   each exposes run(cfg); called by the runners
  validation/             reproducible checks (section 9), run after each stage
    make_synthetic_state.py
  outputs/figures, outputs/tables
```

Additions to the spec's structure: the runner scripts at the top level, `common.py` (shared code), `00_inspect_raw.py`, and the synthetic test state.

**How it runs.** Everything is started from one of the top-level runner scripts, with no arguments, e.g. `python run_texas.py`. Each runner always does the same thing: it runs every stage for its state in order, with the stage's check straight after it, and stops at the first failed check. Nothing needs editing between runs. Stage and check files are not run directly; each holds a `run(cfg)` function that the runners call with the state's config. Everything state-specific is in `config/{state}.py`, so a third state is a new config plus two short runner files, not new code. A comparison of Texas and California together is added as its own step once both states have run.

## Setup (Mac)

1. Create the environment from the repository root:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Versions are pinned for reproducibility and work on Python 3.15 on Apple Silicon. GerryChain is version 1.0, whose API differs from the 0.3 examples in the spec (see choices below).
2. Get a free Census API key at https://api.census.gov/data/key_signup.html (activate it from the confirmation email) and put it in a file called `.env` in the repository root, as one line: `CENSUS_API_KEY=yourkey`. It is gitignored.
3. Run the synthetic test (next section) to confirm everything installs and runs on your machine.

## Synthetic test

```
python run_synthetic_test.py
```

Builds a fake 30 x 30 grid state with 6 districts, in exactly the format stages 02 to 05 will produce, then runs stages 06 to 09 and every check on it. It writes only `synthetic_*` files and figures, never real data. The chains take about a minute. Every check prints `PASS` lines and the run ends with `all steps finished`.

## Downloading the data

`python download_texas.py` (and `download_california.py`) fetches everything available by script from the Census Bureau; run it once. Everything else is downloaded by hand into the folders below. Leave files as they come (zips can stay zipped). The first step of `run_{state}.py` writes `outputs/raw_inspection_{state}.txt`, listing every raw file's columns and first rows; those listings are what stages 02 to 05 are written against.

Portal and file names below are from the spec and should be checked when downloading; the folder names are what the code will expect.

### Texas, needed first (build order step 1)

| Folder | What | Where |
|---|---|---|
| `data/raw/texas/census/` | TIGER 2020 blocks and block groups, 2020 census population and voting-age population by race per block, ACS income and education per block group | `download_texas.py` |
| `data/raw/texas/vtds/` | 2020 VTD shapefile | Texas Legislative Council Capitol Data Portal, data.capitol.texas.gov |
| `data/raw/texas/elections/2022/` | VTD-level returns, 2022 general, statewide races | Capitol Data Portal |
| `data/raw/texas/elections/2024/` | VTD-level returns, 2024 general, statewide races | Capitol Data Portal |
| `data/raw/texas/plans/2021/` | 2021 congressional plan (PLANC2193), block assignment file | Capitol Data Portal |
| `data/raw/texas/plans/2025/` | 2025 congressional plan (PLANC2333), block assignment file | Capitol Data Portal |

### California (build order step 4)

| Folder | What | Where |
|---|---|---|
| `data/raw/california/census/` | as for Texas | `download_california.py` |
| `data/raw/california/elections/2022/` | statement of vote, 2022 general, at 2020 census block level | Statewide Database, statewidedatabase.org |
| `data/raw/california/elections/2024/` | the same for 2024 | Statewide Database |
| `data/raw/california/plans/2021/` | 2021 Citizens Redistricting Commission congressional plan, block assignment file | wedrawthelines.ca.gov or Redistricting Data Hub |
| `data/raw/california/plans/2025/` | Prop 50 congressional plan, block assignment file | Redistricting Data Hub, CA Secretary of State or legislature |

California units are 2020 census block groups, not Statewide Database precincts (see choices), so no precinct shapefile is needed.

### Both states, later (build order step 5 onwards)

| Folder | What | Where |
|---|---|---|
| `data/raw/california/elections/2016/`, `2018/`, `2020/` | Statewide Database precinct results and precinct-to-2010-block conversions | `download_california.py` (the 2021 Redistricting Database's 2020-block versions are linked but return "Not Found"; the Statewide Database has been emailed) |
| `data/raw/california/crosswalk/` | Census 2010-to-2020 block relationship file | `download_california.py` |
| `data/raw/texas/elections/` | all 2012 to 2024 results reported on the 2024 general election VTDs (one zip) | Capitol Data Portal, Comprehensive Election Datasets |
| `data/raw/texas/vtds/` | 2024 primary and general election VTD shapefile (`VTDs_24PG.zip`) | Capitol Data Portal, VTDs |
| `data/raw/texas/plans/2021/`, `2025/` | block equivalency files for PLANC2193 and PLANC2333 | Capitol Data Portal |
| `data/raw/{state}/plans/2010/` | 2010-era enacted map (California's 2011 Commission map, Texas's 2013 court-adopted map) on 2020 census blocks | `download_{state}.py` (Census 2020 block assignment files, 116th Congress) |
| `data/raw/{state}/alarm/` | ALARM Project simulations for the state, benchmark only | alarm-redist.org (Harvard Dataverse) |
| `data/raw/{state}/elections/2026/` | 2026 general returns, once certified | as for 2024 |

## Run order

Build order follows section 9: Texas first, then California, then earlier years and demographics.

1. `python run_synthetic_test.py` once, to confirm the code runs on your machine.
2. `python download_texas.py` once, plus the manual Texas downloads.
3. `python run_texas.py`, which runs these steps in order:

| Stage | Check after it |
|---|---|
| `00_inspect_raw` | |
| `02_build_units` | `check_units` |
| `03_crosswalk` (election results onto 2020 blocks) | `check_crosswalk` |
| `04_attach_votes` (blocks onto units) | |
| `05_enacted_assignments` (also builds the graph) | `check_enacted`, `check_graph` |
| `06_run_ensemble` | `check_ensemble` |
| `07_score_plans` | `check_scores` |
| `08_recentre` | `check_recentre` |
| `09_descriptives` | |

4. The same for California with `download_california.py` and `run_california.py`.

The full Texas ensemble is an overnight job; its five chains run in parallel, one process each.

## Data contract between stages

Stages 06 to 09 rely only on these files, written by stages 02 to 05 (and mimicked by the synthetic state). Units are identified by `idx`, their row number 0 to n-1, because GerryChain 1.0 renumbers graph nodes internally.

| File | Contents |
|---|---|
| `{state}_units.parquet` | one row per unit, ordered by `idx`: `idx`, `unit_id`, `TOTPOP`, `COUNTY`, voting-age population `VAP_HISP`, `VAP_NHWHITE`, `VAP_NHBLACK`, `VAP_NHASIAN`, `VAP_OTHER`, `LOG_MEDINC`, `DEGREE_SHARE`, and `{year}_{race}_D`, `{year}_{race}_R` vote counts for every race listed in the config |
| `{state}_units_geo.parquet` | `unit_id`, `idx`, geometry |
| `{state}_graph.json` | dual graph (networkx adjacency JSON, written by GerryChain) with node attributes `idx`, `TOTPOP`, `COUNTY` |
| `{state}_enacted.parquet` | `idx`, `unit_id`, `plan_2010`, `plan_2021`, `plan_2025`: district labels 0 to k-1 |

`VAP_OTHER` is all remaining voting-age population (American Indian, Pacific Islander, other, two or more races). `LOG_MEDINC` and `DEGREE_SHARE` may be missing (suppressed ACS values); missing units get zero weight in the economic spread measures.

## Measures

For district d with units i, population weights w_i:

- **V** (Democratic two-party share): for each race in the year's composite, district Democratic votes divided by district Democratic plus Republican votes; then the equal-weighted mean across races. Example: one race at 0.40 and one at 0.44 gives V = 0.42.
- **S** (safety) = absolute value of (V minus 0.5). Example: V = 0.40 gives S = 0.10.
- **L** (signed lean towards the mapmaker's party) = V minus 0.5 if the 2025 map was drawn by Democrats (California), 0.5 minus V if by Republicans (Texas). Positive means the district leans towards the party that drew the 2025 map, which flips the sign for California automatically.
- **H** (partisan homogeneity) = population-weighted standard deviation of the units' composite shares within the district. A unit's composite share is its mean two-party share across the races in which it has votes; a unit with no two-party votes at all gets zero weight.
- **R** (racial homogeneity) = sum over the five groups of (group's share of district voting-age population) squared. Example: 80% and 20% gives 0.64 + 0.04 = 0.68.
- **E_INC** = population-weighted standard deviation of log median household income across the district's units.
- **E_DEG** = population-weighted standard deviation of the share of adults 25+ with a bachelor's degree or higher.
- **Seats** = districts with V above 0.5. **Competitive** = districts with S below 0.05.
- **Efficiency gap** = (Democratic seat share minus 0.5) minus 2 times (mean district V minus 0.5). This is the equal-turnout form, needed because a composite has no single vote total. Positive favours Democrats.
- **Mean-median** = median district V minus mean district V. Positive favours Democrats.

Recentring (section 7), for unit i in year t and any measure X:

- **X_it**: the measure for i's district under the map in force in year t, scored with year t votes.
- **mu_it**: the mean of i's district measure across all ensemble plans, scored with year t votes (the geography part).
- **Z_it** = X_it minus mu_it (the mapmaker part). Example: enacted H = 0.08, ensemble mean 0.15, so Z = minus 0.07.
- **p_it**: share of ensemble plans in which i's district has a lower value than under the enacted map, ties counting half. The same direction for every measure: for H a low p means unusually homogeneous; for S a high p means unusually safe. (The spec words the H and S percentiles in opposite directions; one direction for all measures avoids mixing them up.)

## Choices

All normative choices use the spec's suggested defaults except where marked as a departure.

| Choice | Used | Where set |
|---|---|---|
| States (section 3) | Texas and California; a third state is a new config plus runner files | `config/` |
| Elections defining partisan lean (3) | each year's own statewide races, composite within year, equal weights; every race with both a Democratic and a Republican candidate | `elections` in state config |
| ALARM data (3) | built from raw sources; ALARM only as a benchmark | |
| Post-Callais redraws (3) | excluded, discussed in the conclusion | |
| Unit of analysis (4) | Texas: 2020 VTDs. California: 2020 block groups (**departure**: Statewide Database precincts are redrawn every election, so they give no fixed layer across years; its votes already sit on 2020 blocks, so block groups receive them by exact aggregation with no proration) | `unit_type` |
| Proration weights for 2010-era results (4) | none needed so far: California's 2016 to 2020 results come already on 2020 blocks; Texas to be set once its source is known, using the same rule as below if a split is needed | stage 03 |
| Units split by an enacted plan (4) | majority-population assignment, misassigned share reported (see limitations below) | stage 05 |
| Census data source | Census Data API for population, race, income and education; TIGER shapefiles and block assignment files from the Census download site | `01_download.py` |
| Same rules in both states | every choice below applies to Texas and California alike; only the unit type differs (section 4 row above) | |
| Neighbours in the map graph | rook adjacency: units are neighbours only if they share a stretch of border, not just a corner | stage 05 |
| Islands | linked to the nearest unit on the mainland, in the same county where possible, as islands are districted in practice | stage 05 |
| Precinct results onto blocks (California) | split in proportion to registered voters (the Statewide Database's `PCTSRPREC`); Texas results arrive on VTDs, the units, so need no split | stage 04 |
| 2010-era enacted maps | Census 2020 block assignment files (116th Congress): exact on 2020 blocks, no crosswalk | `01_download.py` |
| Income measure | ACS median household income; the "250,000 or more" code kept as 250,001; suppressed values become missing and get zero weight | stage 02 |
| Population counts | standard Census counts in both states, not California's prisoner-reallocated counts | `01_download.py` |
| 2010-era maps in the analysis | scored and compared descriptively; no second ensemble with their district counts, so 2016 to 2020 are not recentred | |
| California 2016 to 2020 results | Statewide Database precinct results on 2010 blocks, moved to 2020 blocks by land-area share (Census crosswalk) | stage 03 |
| Texas units | the Texas Legislative Council's 2024 general election VTDs, on which it re-reports every election from 2012 | stage 02 |
| Ensemble for 2010-era maps (4) | re-use the 2020-geography ensemble; but see open question 1 | |
| Sampling algorithm (5) | ReCom in GerryChain 1.0; SMC in R as a later robustness check | `06_run_ensemble.py` |
| Population tolerance (5) | 1% | `ensemble.pop_tolerance` |
| Compactness (5) | none beyond ReCom's built-in preference | |
| County splits (5) | mild penalty, same in both states: GerryChain's `region_surcharge` of 0.2 on edges between counties, which makes spanning trees less likely to cut them | `ensemble.county_surcharge` |
| Race and VRA (5) | race-blind; a limitation for the 2021 comparison | |
| Ensemble size (5) | 5 chains x 2,000 retained plans = 10,000 | `ensemble` |
| Burn-in and thinning (mechanical) | 100,000 steps per chain, first 20,000 discarded, every 40th kept; revisit after the trace plots | `ensemble` |
| Partisan homogeneity (6) | internal spread H | |
| Racial homogeneity (6) | composition (Herfindahl R); Theil index later as a robustness check | |
| Race groups (6) | Hispanic, non-Hispanic white, non-Hispanic Black, non-Hispanic Asian, other; voting-age population | `common.RACE_GROUPS` |
| Economic measure (6) | both income and degree spread computed | |
| Competitive threshold (6) | continuous S for analysis; S below 0.05 for descriptive counts | `competitive_threshold` |
| Centre (7) | ensemble mean, with percentiles alongside | |
| Votes used each year (7) | that year's results | |
| Signed lean or safety (7) | both computed (S and L) | |
| Demographics over time (7) | 2020 census for race; one ACS vintage (2019 to 2023) for income for now, yearly ACS only if income enters the DiD | `acs_year` |

Further implementation notes:

- **GerryChain 1.0.** The spec's example code is for version 0.3. In 1.0, `MarkovChain` takes `proposal_fn`, `acceptance_fn` and `initial_partition`; `recursive_tree_part` lives in `gerrychain.partition.initial_partition_generators`; each chain gets its own seeded random generator, so every chain is reproducible from its seed; and `node_repeats` is 0, because 1.0 warns that repeats bring no benefit with its default cut finder.
- **Every enacted map is scored under every year's votes**, not only the years it was in force, so maps can be compared on the same voters. Single-year descriptives use the latest year with results and compare the 2021 and 2025 maps on those same votes.
- **Sorted-district box plots** sort each measure by its own value within each plan (the standard form).
- **Averages over units** in the geography-versus-mapmaker figure are population-weighted.
- **Starting plans** are drawn at random, not from an enacted map, so the ensemble does not inherit a gerrymander.
- **Only plan assignments are stored** (`data/processed/{state}_ensemble/chain_{seed}.npz`, compressed numpy); new measures need only stage 07 rerun.

## Open questions

1. **District counts differ by era.** Decided: the 2010-era maps and 2016 to 2020 elections are included and compared descriptively only; stages 07 to 09 are to be adjusted so 2016 to 2020 skip recentring instead of stopping. The 2010-era maps have 36 districts in Texas and 53 in California; the 2020-geography ensemble has 38 and 52. Recentring a 36-district map against a 38-district ensemble is not meaningful, so `08_recentre.py` stops with an error if a year's map does not match the ensemble's district count. To be decided before build step 5: either a second ensemble on the same 2020 graph with the 2010-era district count (reruns stage 06 only), or leaving 2016 to 2020 out of the recentred panel.
2. **ALARM comparison** in `check_ensemble.py` is added once the ALARM files are downloaded and their format is known.
3. **Quick Texas run.** The spec's build order runs a short chain on real Texas data before the overnight ensemble, to catch problems early. Whether to add it as a separate check is decided once stages 02 to 05 exist.

## Data choices and their limitations

**Neighbours (rook adjacency).** Two units count as neighbours only if they share a stretch of border. Units meeting at a single corner are not, which stops a district being joined at a point. This is the standard in the ensemble literature; it slightly narrows the set of possible plans compared with also counting corners, with negligible effect at block group and VTD scale.

**Islands.** State constitutions, California's included, require contiguous districts, and courts accept land separated by water as contiguous; in practice mapmakers always place an island with a district on the nearby coast. The graph mirrors this: after neighbours are found, any part of the state not connected to the rest is linked to the nearest mainland unit, in the same county where one exists. Limitation: "nearest" stands in for the real-world tie (a ferry route, a bridge, a county seat), so an island may be linked to a slightly different stretch of coast than a mapmaker would choose. The islands concerned hold few people (Catalina about 4,000; most Channel Islands almost none), so the effect is negligible. `check_graph` reports every link added and the population it carries.

**Units split by an enacted map.** The ensemble moves whole units (block groups in California, VTDs in Texas), but enacted maps are drawn from census blocks, so an enacted boundary sometimes cuts through a unit. To score the enacted map on the same units as the ensemble, each split unit is given whole to the district holding most of its population (a unit with no population goes to the district holding most of its blocks). `check_enacted` fails if any map moves 1% or more of the state's population, which would point to a mismatched file rather than ordinary splits. Limitation: the enacted map as scored differs slightly from the real one. `check_enacted` reports, for every map, the number of split units and the share of the state's population placed in a different district from the real map.

**Precinct results onto blocks (California).** Results are reported by precinct, and the Statewide Database splits each precinct's votes across its census blocks in proportion to registered voters. Limitation: this assumes a precinct's votes are spread across its blocks like its registered voters, though turnout and party lean can vary block to block. The error stays within precincts of a few thousand voters, so it largely cancels once blocks add up to block groups and districts. Vote cells the Statewide Database leaves non-numeric (masked small counts) are counted as zero; stage 03 prints how many there are each year. Texas results are reported on VTDs, which are its units, so nothing is split.

**2010-era enacted maps.** Taken from the Census Bureau's 2020 block assignment files, which give every 2020 census block's congressional district under the maps in force in 2020: California's 2011 Commission map (53 districts) and Texas's 2013 court-adopted map (36). 2020 blocks were drawn to follow these district lines, so the assignment is essentially exact (where the Census had to split a block, it assigned it whole to one district), and no 2010-to-2020 block crosswalk is needed. Limitation: these maps were drawn on 2010 census populations but are scored here on 2020 populations and units, so their districts look less equal in population than when drawn, and the 2020-geography ensemble is not quite the counterfactual their mapmakers faced. Their district counts also differ from the ensemble's (open question 1).

**California results for 2016 to 2020.** The Statewide Database's 2020-block versions are listed but their links are broken, so these years use its precinct results with its registration-based conversion onto 2010 blocks, then the Census 2010-to-2020 block relationship file, splitting each 2010 block's votes across the 2020 blocks it overlaps in proportion to shared land area. Limitation: the second step assumes voters are spread evenly over land within a 2010 block. It matters only where blocks were redrawn between censuses; most barely changed and blocks are tiny, so the error is small, but it is one more approximation than 2022 and 2024 carry. `check_crosswalk` reports the votes kept at each step.

**Texas units.** The Texas Legislative Council re-reports every election from 2012 to 2024 on its 2024 general election VTDs, so those VTDs are the fixed units across all years (rather than the Census Bureau's 2020 VTDs, on which 2022 and 2024 results are not published). Limitation: the Council's reallocation of older results onto 2024 VTDs is its own method and is taken as given.

**Income.** Median household income per block group from the ACS 2019 to 2023 five-year estimates. The Census reports "250,000 or more" as the code 250,001, and suppressed values as large negative codes, which become missing (zero weight in the spread measures). Limitation: the top code compresses differences among the richest areas, so income spread is understated in districts containing them; block group ACS estimates also carry wide margins of error.

**Different units in the two states.** Each state's units are the smallest fixed geography its official results can be placed on without guesswork beyond the method above: VTDs in Texas, where results are reported on them; block groups in California, whose precincts change every election. Limitation: units differ in size between the states, so the two ensembles are not built from identical building blocks; `check_units` reports unit counts and population sizes for both.

## Limitations to state (section 7)

The ensemble defines the counterfactual, so results depend on the constraints above. Recentring assumes the enacted plan is comparable to a draw from the ensemble apart from the mapmaker's deviation, while a gerrymander is deliberately non-random. ReCom's implied distribution is not formally defined. The race-blind ensemble means part of the 2021 baseline's gap reflects VRA obligations, not partisanship.