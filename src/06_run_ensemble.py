# Stage 06: build the neutral ensemble for one state (spec section 5). Called by run_{state}.py.
# One ReCom chain per seed, run in parallel. Only plan assignments are stored; every district
# property is computed later (07), so new measures never require re-running chains.
#
# Choices (spec section 5 defaults):
#   sampling algorithm: ReCom in GerryChain (its implied distribution is not formally defined;
#                       stated as a limitation, SMC in R as a later robustness check)
#   population tolerance: 1% of the ideal district population (config ensemble.pop_tolerance)
#   compactness: none beyond ReCom's built-in preference for compact districts
#   county splits: mild penalty, same in both states, via GerryChain's region_surcharge, which
#                  makes spanning trees less likely to cut edges between counties
#   race and VRA: race-blind, no majority-minority constraint
#   ensemble size: 5 chains x 2,000 retained plans (config ensemble.full)
#
# GerryChain 1.0 notes: MarkovChain arguments are proposal_fn / acceptance_fn / initial_partition,
# randomness comes from an explicit rng per chain (so every chain is reproducible from its seed),
# and node_repeats is 0 because 1.0 warns that repeats bring no benefit with its default cut finder.

import random
from functools import partial
from multiprocessing import Pool

import numpy as np
from gerrychain import Graph, MarkovChain, Partition
from gerrychain.accept import always_accept
from gerrychain.constraints import within_percent_of_ideal_population
from gerrychain.partition.initial_partition_generators import recursive_tree_part
from gerrychain.proposals import recom
from gerrychain.updaters import Tally

from common import paths


def run_chain(cfg, seed):
    ens = cfg["ensemble"]
    k = cfg["n_districts"]
    tol = ens["pop_tolerance"]
    rng = random.Random(seed)

    graph = Graph.from_json(str(paths(cfg)["graph"]))
    ideal = sum(graph.node_data(n)["TOTPOP"] for n in graph.nodes) / k

    # Random starting plan rather than an enacted map, so the chain does not inherit a gerrymander
    seed_plan = recursive_tree_part(graph, range(k), ideal, "TOTPOP", tol, rng=rng)
    initial = Partition(graph, assignment=seed_plan,
                        updaters={"population": Tally("TOTPOP", alias="population")})

    proposal = partial(recom, pop_col="TOTPOP", pop_target=ideal, epsilon=tol,
                       node_repeats=0, region_surcharge={"COUNTY": ens["county_surcharge"]})
    chain = MarkovChain(proposal_fn=proposal,
                        constraints=[within_percent_of_ideal_population(initial, tol)],
                        acceptance_fn=always_accept, initial_partition=initial,
                        total_steps=ens["steps"], rng=rng)

    # Map GerryChain's internal node ids to unit idx once; each plan becomes an integer
    # array of district labels in units-table order
    nodes = list(initial.graph.nodes)
    idx = np.array([initial.graph.node_data(n)["idx"] for n in nodes])
    kept, steps = [], []
    for i, plan in enumerate(chain):
        if i >= ens["burn_in"] and (i - ens["burn_in"]) % ens["thin"] == 0:
            labels = np.empty(len(nodes), dtype=np.int16)
            labels[idx] = [plan.assignment[n] for n in nodes]
            kept.append(labels)
            steps.append(i)
        if i % 1000 == 0:
            print(f"{cfg['name']} chain {seed}: step {i} of {ens['steps']}", flush=True)

    out = paths(cfg)["ensemble_dir"] / f"chain_{seed}.npz"
    np.savez_compressed(out, plans=np.column_stack(kept), steps=np.array(steps), seed=seed)
    print(f"{cfg['name']} chain {seed}: saved {len(kept)} plans to {out.name}", flush=True)


def run(cfg):
    d = paths(cfg)["ensemble_dir"]
    d.mkdir(parents=True, exist_ok=True)
    # Old chain files are removed so a rerun never mixes with an earlier ensemble
    for f in d.glob("chain_*.npz"):
        f.unlink()
    seeds = cfg["ensemble"]["seeds"]
    # One process per chain, all running at once
    with Pool(len(seeds)) as pool:
        pool.starmap(run_chain, [(cfg, s) for s in seeds])
