import numpy as np
from .science import utility, welfare, probability, update, posterior_summary
from .constraints import consistent_set, intersect, switch_diagnostics


def infer(bank, trials):
    common = bank.prior.copy()
    grids = {}
    sets = {}
    verified = True
    switch = None
    for i, t in enumerate(trials):
        if t.get("response") not in [0, 1]:
            continue
        g = bank.lookup[t["group_id"]]
        grid = g["grid"]
        curves = bank.curves(g)
        likelihood = probability(curves[t["a"]], curves[t["b"]], bank.settings)
        common = update(common, likelihood, t["response"])
        grids[grid] = update(
            grids.get(grid, bank.prior.copy()), likelihood, t["response"]
        )
        u = utility(bank.temperatures[[t["a"], t["b"]]], g["desired"], bank.settings)
        cs = consistent_set(u[0], u[1], t["response"], bank.settings.root_tolerance)
        verified = verified and cs["converged"]
        sets[grid] = intersect(sets.get(grid, [[0, None]]), cs["intervals"])
        diag = switch_diagnostics(sets, verified)
        if diag["trigger_B"] and switch is None:
            switch = dict(
                trial=i + 1,
                witness=diag["witness"],
                timestamp=t.get("answered_at"),
                sets={k: sets[k] for k in diag["witness"]},
            )
    diag = switch_diagnostics(sets, verified)
    diag["switch_witness"] = switch
    all_grids = sorted({g["grid"] for g in bank.groups})
    summaries = {
        g: posterior_summary(
            bank.nodes,
            grids.get(g, bank.prior),
            bank.settings.posterior_mass,
            sum(
                1
                for t in trials
                if t.get("response") in [0, 1]
                and bank.lookup[t["group_id"]]["grid"] == g
            ),
        )
        for g in all_grids
    }
    return dict(
        stage="CONTEXTUAL" if switch else "COMMON",
        common=posterior_summary(
            bank.nodes,
            common,
            bank.settings.posterior_mass,
            sum(t.get("response") in [0, 1] for t in trials),
        ),
        grids=summaries,
        deterministic=diag,
        grid_sets=sets,
        likelihood_assumptions=dict(
            kappa=bank.settings.choice_kappa,
            lapse=bank.settings.choice_lapse,
            calibrated=False,
        ),
        config_hash=bank.settings.fingerprint,
    )


def sensitivity(bank, trials):
    from .science import quadrature

    variants = [
        dict(name="beta_2_2", prior_family="beta", prior_alpha=2, prior_beta=2),
        dict(name="beta_half", prior_family="beta", prior_alpha=0.5, prior_beta=0.5),
        dict(name="kappa_15", choice_kappa=15),
        dict(name="kappa_60", choice_kappa=60),
        dict(name="lapse_0_10", choice_lapse=0.1),
        dict(name="q_32", q_quadrature_count=32),
        dict(name="q_128", q_quadrature_count=128),
    ]
    output = []
    for variant in variants:
        name = variant["name"]
        config = bank.settings.model_copy(
            update={k: v for k, v in variant.items() if k != "name"}
        )
        nodes, posterior = quadrature(config)
        for t in trials:
            if t.get("response") not in [0, 1]:
                continue
            g = bank.lookup[t["group_id"]]
            u = utility(bank.temperatures[[t["a"], t["b"]]], g["desired"], config)
            w = np.array([welfare(u, e) for e in nodes])
            p = probability(w[:, 0], w[:, 1], config)
            posterior = update(posterior, p, t["response"])
        output.append(
            dict(
                name=name,
                settings=config.model_dump(),
                posterior=posterior_summary(
                    nodes,
                    posterior,
                    config.posterior_mass,
                    sum(t.get("response") in [0, 1] for t in trials),
                ),
            )
        )
    return output
