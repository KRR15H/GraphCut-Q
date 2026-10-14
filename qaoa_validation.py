
import csv
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from qaoa_solver import EDGES, NUM_VERTICES, find_exact_optimum

# ---------------- CONFIGURATION ----------------
DEPTHS = [1, 2, 3]
SEEDS = list(range(1001, 1021))  # 20 independent seeds
SHOTS = 4096
MAX_ITERATIONS = 200

PARAM_FILE = Path("qaoa_best_parameters.npz")
CSV_FILE = Path("qaoa_validation_results.csv")

BASIS_GATES = ["rz", "sx", "x", "cx"]

PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]


# ---------------- GRAPH ----------------
def cut_weight(bits):
    return sum(
        weight
        for u, v, weight in EDGES
        if bits[u] != bits[v]
    )


# ---------------- QAOA CIRCUIT ----------------
def make_circuit(gammas, betas, measured=False):
    qc = QuantumCircuit(NUM_VERTICES)
    qc.h(range(NUM_VERTICES))

    for gamma, beta in zip(gammas, betas):
        for u, v, weight in EDGES:
            qc.rzz(-gamma * weight, u, v)

        for q in range(NUM_VERTICES):
            qc.rx(2 * beta, q)

    if measured:
        qc.measure_all()

    return qc


def expected_cut(params, p):
    gammas = params[:p]
    betas = params[p:]

    state = Statevector.from_instruction(
        make_circuit(gammas, betas)
    )

    expectation = 0.0

    for index, probability in enumerate(state.probabilities()):
        bits = format(index, f"0{NUM_VERTICES}b")[::-1]
        expectation += probability * cut_weight(bits)

    return float(expectation)


# ---------------- PARAMETER PREPARATION ----------------
def load_or_prepare_parameters():
    if PARAM_FILE.exists():
        saved = np.load(PARAM_FILE)
        params = {p: saved[f"p{p}"].copy() for p in DEPTHS}
        print(f"Loaded saved parameters from {PARAM_FILE}")
        return params

    print("\nNo saved parameter file found.")
    print("Preparing parameters ONCE before validation.")
    print("These preparation runs are not validation runs.\n")

    rng = np.random.default_rng(2026)
    params = {}

    for p in DEPTHS:
        best_value = -float("inf")
        best_params = None

        # One preparation optimization per depth.
        # Validation below never calls the optimizer.
        initial = np.concatenate([
            rng.uniform(0, 2 * np.pi, p),
            rng.uniform(0, np.pi, p),
        ])

        result = minimize(
            lambda x: -expected_cut(x, p),
            initial,
            method="COBYLA",
            options={
                "maxiter": MAX_ITERATIONS,
                "rhobeg": 0.5,
            },
        )

        candidate_value = -result.fun
        if candidate_value > best_value:
            best_value = candidate_value
            best_params = result.x.copy()

        params[p] = best_params
        print(
            f"Prepared p={p}: "
            f"expected cut={best_value:.4f}"
        )

    np.savez(
        PARAM_FILE,
        **{f"p{p}": params[p] for p in DEPTHS},
    )

    print(f"Saved fixed parameters to {PARAM_FILE}")
    return params


# ---------------- NOISE MODEL ----------------
def make_noise_model():
    model = NoiseModel()

    model.add_all_qubit_quantum_error(
        depolarizing_error(0.001, 1),
        ["rz", "sx", "x"],
    )

    model.add_all_qubit_quantum_error(
        depolarizing_error(0.005, 2),
        ["cx"],
    )

    model.add_all_qubit_readout_error(
        ReadoutError([
            [0.99, 0.01],
            [0.01, 0.99],
        ])
    )

    return model


# ---------------- COUNT EVALUATION ----------------
def evaluate_counts(counts, optimum):
    total = sum(counts.values())
    total_cut = 0
    optimal_count = 0
    best_cut = 0

    for outcome, count in counts.items():
        # Qiskit count strings display the highest classical bit first.
        bits = outcome.replace(" ", "")[::-1][:NUM_VERTICES]
        value = cut_weight(bits)

        total_cut += value * count
        best_cut = max(best_cut, value)

        if value == optimum:
            optimal_count += count

    return {
        "mean_cut": total_cut / total,
        "best_cut": best_cut,
        "optimal_probability": optimal_count / total,
    }


def mean_sd(values):
    # Sample standard deviation across the 20 seed-level means.
    return float(np.mean(values)), float(np.std(values, ddof=1))


# ---------------- VALIDATION ----------------
def main():
    optimum, _ = find_exact_optimum()
    parameters = load_or_prepare_parameters()

    coupling_map = []
    for u, v in PROCESSOR_B_EDGES:
        coupling_map.extend([[u, v], [v, u]])

    ideal_sim = AerSimulator(basis_gates=BASIS_GATES)
    noisy_sim = AerSimulator(
        noise_model=make_noise_model(),
        basis_gates=BASIS_GATES,
    )

    results = []

    print("\n" + "=" * 68)
    print("FIXED-PARAMETER QAOA VALIDATION")
    print(f"Exact optimum: {optimum}")
    print(f"Seeds: {len(SEEDS)} | Shots per seed: {SHOTS}")
    print("No optimization will occur inside the validation loop.")
    print("=" * 68)

    for p in DEPTHS:
        fixed = parameters[p]
        gammas = fixed[:p]
        betas = fixed[p:]

        circuit = make_circuit(gammas, betas, measured=True)

        compiled = transpile(
            circuit,
            basis_gates=BASIS_GATES,
            coupling_map=coupling_map,
            optimization_level=1,
            seed_transpiler=42,
        )

        ideal_means = []
        noisy_means = []
        ideal_opt_probs = []
        noisy_opt_probs = []
        ideal_best = []
        noisy_best = []

        for seed in SEEDS:
            ideal_counts = ideal_sim.run(
                compiled,
                shots=SHOTS,
                seed_simulator=seed,
            ).result().get_counts()

            noisy_counts = noisy_sim.run(
                compiled,
                shots=SHOTS,
                seed_simulator=seed,
            ).result().get_counts()

            ideal = evaluate_counts(ideal_counts, optimum)
            noisy = evaluate_counts(noisy_counts, optimum)

            ideal_means.append(ideal["mean_cut"])
            noisy_means.append(noisy["mean_cut"])
            ideal_opt_probs.append(ideal["optimal_probability"])
            noisy_opt_probs.append(noisy["optimal_probability"])
            ideal_best.append(ideal["best_cut"])
            noisy_best.append(noisy["best_cut"])

        ideal_mean, ideal_sd = mean_sd(ideal_means)
        noisy_mean, noisy_sd = mean_sd(noisy_means)
        ideal_prob, ideal_prob_sd = mean_sd(ideal_opt_probs)
        noisy_prob, noisy_prob_sd = mean_sd(noisy_opt_probs)

        row = {
            "p": p,
            "fixed_expected_cut": expected_cut(fixed, p),
            "approximation_ratio": expected_cut(fixed, p) / optimum,
            "circuit_depth": compiled.depth(),
            "cx_count": compiled.count_ops().get("cx", 0),
            "ideal_mean_cut": ideal_mean,
            "ideal_sd_cut": ideal_sd,
            "noisy_mean_cut": noisy_mean,
            "noisy_sd_cut": noisy_sd,
            "noise_gap": ideal_mean - noisy_mean,
            "ideal_optimal_probability": ideal_prob,
            "ideal_optimal_probability_sd": ideal_prob_sd,
            "noisy_optimal_probability": noisy_prob,
            "noisy_optimal_probability_sd": noisy_prob_sd,
            "ideal_mean_best_cut": np.mean(ideal_best),
            "noisy_mean_best_cut": np.mean(noisy_best),
        }
        results.append(row)

        print(f"\n--- p={p} ---")
        print(f"Fixed expected cut: {row['fixed_expected_cut']:.4f}")
        print(f"Approximation ratio: {row['approximation_ratio']:.4f}")
        print(f"Circuit depth: {row['circuit_depth']}")
        print(f"CX gates: {row['cx_count']}")
        print(f"Ideal mean cut: {ideal_mean:.4f} +/- {ideal_sd:.4f}")
        print(f"Noisy mean cut: {noisy_mean:.4f} +/- {noisy_sd:.4f}")
        print(f"Ideal - noisy mean: {ideal_mean - noisy_mean:.4f}")
        print(
            "Ideal optimal probability: "
            f"{ideal_prob:.4%} +/- {ideal_prob_sd:.4%}"
        )
        print(
            "Noisy optimal probability: "
            f"{noisy_prob:.4%} +/- {noisy_prob_sd:.4%}"
        )
        print(f"Mean best sampled cut, ideal: {np.mean(ideal_best):.4f}")
        print(f"Mean best sampled cut, noisy: {np.mean(noisy_best):.4f}")

    with CSV_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys(),
        )
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 68)
    print("SUMMARY")
    print("Depth | Ideal mean +/- SD | Noisy mean +/- SD | CX | Circuit depth")

    for row in results:
        print(
            f"{row['p']:>5} | "
            f"{row['ideal_mean_cut']:.4f} +/- {row['ideal_sd_cut']:.4f} | "
            f"{row['noisy_mean_cut']:.4f} +/- {row['noisy_sd_cut']:.4f} | "
            f"{row['cx_count']:>3} | {row['circuit_depth']}"
        )

    winner = max(results, key=lambda r: r["noisy_mean_cut"])
    print(f"\nHighest observed noisy mean: p={winner['p']}")
    print(f"Saved results to {CSV_FILE}")


if __name__ == "__main__":
    main()
