
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from qaoa_solver import EDGES, NUM_VERTICES, find_exact_optimum


# ================= CONFIGURATION =================

DEPTHS = [1, 2, 3]
RESTARTS = 20
MAX_ITERATIONS = 300

SHOTS = 4096
HOLDOUT_SEEDS = list(range(2001, 2031))  # 30 independent seeds
OPTIMIZATION_SEED = 20261014

PARAM_FILE = Path("qaoa_strong_parameters.npz")
OPTIMIZATION_FILE = Path("qaoa_optimization_log.csv")
SEED_RESULTS_FILE = Path("qaoa_strong_seed_results.csv")
SUMMARY_FILE = Path("qaoa_strong_summary.csv")
METADATA_FILE = Path("qaoa_strong_metadata.json")

BASIS_GATES = ["rz", "sx", "x", "cx"]

PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]


# ================= GRAPH =================

def cut_weight(bits):
    return sum(
        weight
        for u, v, weight in EDGES
        if bits[u] != bits[v]
    )


# ================= QAOA =================

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


# ================= NOISE =================

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


# ================= OPTIMIZATION =================

def optimize_all_depths():
    rng = np.random.default_rng(OPTIMIZATION_SEED)
    best_parameters = {}
    optimization_rows = []

    for p in DEPTHS:
        print(f"\nOptimizing p={p}: {RESTARTS} restarts")

        best_value = -float("inf")
        best_params = None

        for restart in range(RESTARTS):
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

            value = -float(result.fun)

            optimization_rows.append({
                "p": p,
                "restart": restart + 1,
                "expected_cut": value,
                "iterations": getattr(result, "nfev", None),
                "success_flag": result.success,
                "message": str(result.message),
            })

            print(
                f"  Restart {restart + 1:02d}/{RESTARTS}: "
                f"expected cut={value:.5f}"
            )

            if value > best_value:
                best_value = value
                best_params = result.x.copy()

        best_parameters[p] = best_params

        print(
            f"Best p={p}: {best_value:.5f}; "
            f"ratio={best_value / find_exact_optimum()[0]:.4f}"
        )

    with open(OPTIMIZATION_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=optimization_rows[0].keys()
        )
        writer.writeheader()
        writer.writerows(optimization_rows)

    np.savez(
        PARAM_FILE,
        **{f"p{p}": best_parameters[p] for p in DEPTHS},
    )

    print(f"\nSaved fixed parameters: {PARAM_FILE}")
    print(f"Saved optimizer log: {OPTIMIZATION_FILE}")

    return best_parameters


# ================= RESULTS =================

def evaluate_counts(counts, optimum):
    total = sum(counts.values())
    weighted_cut = 0
    optimal_count = 0
    best_cut = 0

    for outcome, count in counts.items():
        # Reverse Qiskit's displayed classical-bit order.
        bits = outcome.replace(" ", "")[::-1][:NUM_VERTICES]
        value = cut_weight(bits)

        weighted_cut += value * count
        best_cut = max(best_cut, value)

        if value == optimum:
            optimal_count += count

    return {
        "mean_cut": weighted_cut / total,
        "best_cut": best_cut,
        "optimal_probability": optimal_count / total,
    }


def mean_sd_ci(values):
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1))
    # Approximate 95% t interval for 30 seed-level observations.
    margin = 2.045 * sd / np.sqrt(len(values))

    return mean, sd, mean - margin, mean + margin


# ================= HOLDOUT VALIDATION =================

def validate(best_parameters, optimum):
    coupling_map = []
    for u, v in PROCESSOR_B_EDGES:
        coupling_map.extend([[u, v], [v, u]])

    ideal_sim = AerSimulator(basis_gates=BASIS_GATES)
    noisy_sim = AerSimulator(
        noise_model=make_noise_model(),
        basis_gates=BASIS_GATES,
    )

    seed_rows = []
    summary_rows = []

    for p in DEPTHS:
        params = best_parameters[p]
        gammas = params[:p]
        betas = params[p:]

        circuit = make_circuit(gammas, betas, measured=True)

        compiled = transpile(
            circuit,
            basis_gates=BASIS_GATES,
            coupling_map=coupling_map,
            optimization_level=1,
            seed_transpiler=42,
        )

        ideal_means, noisy_means = [], []
        ideal_probs, noisy_probs = [], []
        ideal_best, noisy_best = [], []

        print(f"\nHoldout validation: p={p}")

        for seed in HOLDOUT_SEEDS:
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
            ideal_probs.append(ideal["optimal_probability"])
            noisy_probs.append(noisy["optimal_probability"])
            ideal_best.append(ideal["best_cut"])
            noisy_best.append(noisy["best_cut"])

            seed_rows.append({
                "p": p,
                "seed": seed,
                "shots": SHOTS,
                "ideal_mean_cut": ideal["mean_cut"],
                "noisy_mean_cut": noisy["mean_cut"],
                "ideal_optimal_probability": ideal["optimal_probability"],
                "noisy_optimal_probability": noisy["optimal_probability"],
                "ideal_best_cut": ideal["best_cut"],
                "noisy_best_cut": noisy["best_cut"],
            })

        im, isd, ilo, ihi = mean_sd_ci(ideal_means)
        nm, nsd, nlo, nhi = mean_sd_ci(noisy_means)
        ip, ipsd, iplo, iphi = mean_sd_ci(ideal_probs)
        np_, npsd, nplo, nphi = mean_sd_ci(noisy_probs)

        expected = expected_cut(params, p)
        cx = compiled.count_ops().get("cx", 0)

        summary_rows.append({
            "p": p,
            "fixed_expected_cut": expected,
            "approximation_ratio": expected / optimum,
            "circuit_depth": compiled.depth(),
            "cx_count": cx,
            "ideal_mean": im,
            "ideal_sd": isd,
            "ideal_ci95_low": ilo,
            "ideal_ci95_high": ihi,
            "noisy_mean": nm,
            "noisy_sd": nsd,
            "noisy_ci95_low": nlo,
            "noisy_ci95_high": nhi,
            "noise_gap": im - nm,
            "ideal_optimal_probability": ip,
            "ideal_optimal_probability_sd": ipsd,
            "ideal_optimal_ci95_low": iplo,
            "ideal_optimal_ci95_high": iphi,
            "noisy_optimal_probability": np_,
            "noisy_optimal_probability_sd": npsd,
            "noisy_optimal_ci95_low": nplo,
            "noisy_optimal_ci95_high": nphi,
            "ideal_mean_best_cut": float(np.mean(ideal_best)),
            "noisy_mean_best_cut": float(np.mean(noisy_best)),
        })

        print(
            f"Ideal: {im:.4f} +/- {isd:.4f} "
            f"(approx. 95% CI {ilo:.4f} to {ihi:.4f})"
        )
        print(
            f"Noisy: {nm:.4f} +/- {nsd:.4f} "
            f"(approx. 95% CI {nlo:.4f} to {nhi:.4f})"
        )
        print(f"Noise gap: {im - nm:.4f}")
        print(f"Noisy optimal probability: {np_:.3%}")
        print(f"CX={cx}, depth={compiled.depth()}")

    with open(SEED_RESULTS_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=seed_rows[0].keys())
        writer.writeheader()
        writer.writerows(seed_rows)

    with open(SUMMARY_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nFINAL HOLDOUT SUMMARY")
    for row in summary_rows:
        print(
            f"p={row['p']} | noisy mean={row['noisy_mean']:.4f} "
            f"+/- {row['noisy_sd']:.4f} | "
            f"CX={row['cx_count']} | depth={row['circuit_depth']}"
        )

    winner = max(summary_rows, key=lambda r: r["noisy_mean"])
    print(f"\nHighest holdout noisy mean: p={winner['p']}")
    print(f"Saved seed-level results: {SEED_RESULTS_FILE}")
    print(f"Saved summary: {SUMMARY_FILE}")

    return summary_rows


def main():
    optimum, optimal_bits = find_exact_optimum()

    metadata = {
        "vertices": NUM_VERTICES,
        "edges": [list(edge) for edge in EDGES],
        "exact_optimum": optimum,
        "one_optimal_bitstring": str(optimal_bits),
        "depths": DEPTHS,
        "restarts_per_depth": RESTARTS,
        "max_optimizer_iterations": MAX_ITERATIONS,
        "shots_per_seed": SHOTS,
        "holdout_seeds": HOLDOUT_SEEDS,
        "optimization_seed": OPTIMIZATION_SEED,
        "transpile_optimization_level": 1,
        "transpile_seed": 42,
        "basis_gates": BASIS_GATES,
        "single_qubit_depolarizing_probability": 0.001,
        "cx_depolarizing_probability": 0.005,
        "readout_flip_probability": 0.01,
    }

    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Exact optimum: {optimum}")
    print("Phase 1: optimize parameters.")
    parameters = optimize_all_depths()

    print("\nPhase 2: freeze parameters and run holdout validation.")
    print("No optimizer is called in the validation phase.")
    validate(parameters, optimum)

    print(f"\nSaved experiment metadata: {METADATA_FILE}")


if __name__ == "__main__":
    main()
