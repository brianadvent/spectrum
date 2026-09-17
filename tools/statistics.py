"""SPE statistics adapted from Daniel Autenrieth's 2026 comparison analysis. MIT."""
from collections import Counter
import itertools
import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

def outcome_scores(preferences: dict[str, float], keys: list[str], outcome_ids: list[str]) -> dict[str, float]:
    wins: Counter = Counter()
    totals: Counter = Counter()
    for key in keys:
        a, b = key.split("|")
        p = preferences[key]
        wins[a] += p
        totals[a] += 1
        wins[b] += 1 - p
        totals[b] += 1
    return {outcome_id: wins[outcome_id] / totals[outcome_id] for outcome_id in outcome_ids}


def fit_thurstone(preferences: dict[str, float], keys: list[str], outcome_ids: list[str]) -> dict:
    index = {outcome_id: i for i, outcome_id in enumerate(outcome_ids)}
    i_idx = np.array([index[key.split("|")[0]] for key in keys], dtype=int)
    j_idx = np.array([index[key.split("|")[1]] for key in keys], dtype=int)
    observed = np.array([preferences[key] for key in keys], dtype=float)
    scores = outcome_scores(preferences, keys, outcome_ids)
    initial = norm.ppf(np.clip([scores[x] for x in outcome_ids], 0.01, 0.99))
    initial = initial - initial[-1]

    def objective(x: np.ndarray) -> tuple[float, np.ndarray]:
        mu = np.concatenate([x, [0.0]])
        z = (mu[i_idx] - mu[j_idx]) / math.sqrt(2)
        predicted = np.clip(norm.cdf(z), 1e-10, 1 - 1e-10)
        loss = -np.sum(observed * np.log(predicted) + (1 - observed) * np.log(1 - predicted))
        dz = (predicted - observed) * norm.pdf(z) / (predicted * (1 - predicted))
        edge_gradient = dz / math.sqrt(2)
        gradient = np.zeros(len(outcome_ids), dtype=float)
        np.add.at(gradient, i_idx, edge_gradient)
        np.add.at(gradient, j_idx, -edge_gradient)
        return float(loss), gradient[:-1]

    result = minimize(
        objective,
        initial[:-1],
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 2_000, "ftol": 1e-12},
    )
    mu = np.concatenate([result.x, [0.0]])
    mu -= np.mean(mu)
    predicted = norm.cdf((mu[i_idx] - mu[j_idx]) / math.sqrt(2))
    eligible = observed != 0.5
    accuracy = float(np.mean((predicted[eligible] > 0.5) == (observed[eligible] > 0.5))) if np.any(eligible) else None
    return {
        "converged": bool(result.success),
        "message": str(result.message),
        "negative_log_likelihood": float(result.fun),
        "direction_accuracy_excluding_ties": accuracy,
        "legacy_direction_accuracy_including_ties_as_not_A": float(np.mean(
            (predicted > 0.5) == (observed > 0.5)
        )),
        "mean_absolute_probability_error": float(np.mean(np.abs(predicted - observed))),
        "utilities": {outcome_id: float(mu[i]) for i, outcome_id in enumerate(outcome_ids)},
    }


def exact_transitivity(preferences: dict[str, float], outcome_ids: list[str]) -> dict:
    evaluable = cycles = ties_or_missing = 0
    for i, j, k in itertools.combinations(range(len(outcome_ids)), 3):
        keys = (
            f"{outcome_ids[i]}|{outcome_ids[j]}",
            f"{outcome_ids[j]}|{outcome_ids[k]}",
            f"{outcome_ids[i]}|{outcome_ids[k]}",
        )
        if any(key not in preferences for key in keys):
            ties_or_missing += 1
            continue
        p_ab, p_bc, p_ac = (preferences[key] for key in keys)
        if 0.5 in (p_ab, p_bc, p_ac):
            ties_or_missing += 1
            continue
        ab, bc, ac = p_ab > 0.5, p_bc > 0.5, p_ac > 0.5
        evaluable += 1
        cycles += int((ab and bc and not ac) or ((not ab) and (not bc) and ac))
    return {
        "all_possible_triplets": math.comb(len(outcome_ids), 3),
        "evaluable_strict_majority_triplets": evaluable,
        "ties_or_missing_triplets": ties_or_missing,
        "intransitive_cycles": cycles,
        "transitive_triplets": evaluable - cycles,
        "transitivity_rate": (evaluable - cycles) / evaluable if evaluable else None,
    }

