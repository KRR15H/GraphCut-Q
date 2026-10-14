
import csv
import numpy as np

from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from qaoa_solver import EDGES, NUM_VERTICES, find_exact_optimum

DEPTHS = [1, 2, 3]
RESTARTS = 5
MAX_ITERATIONS = 200
SHOTS = 4096
SEEDS = [11, 22, 33, 44, 55]

BASIS_GATES = ["rz", "sx", "x", "cx"]
PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]


def cut_weight(bits):
    return sum(
        w for u, v, w in EDGES if bits[u] != bits[v]
    )


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

    probabilities = state.probabilities()
    expectation = 0.0

    for index, probability in enumerate(probabilities):
        bits = format(index, f"0{NUM_VERTICES}b")[::-1]
        expectation += probability * cut_weight(bits)

    return float(expectation)


def make_noise_model():
    model = NoiseModel()
    model.add_all_qubit_quantum_error(
        depolarizing_error(0.001, 1), ["rz", "sx", "x"]
    )
    model.add_all_qubit_quantum_error(
        depolarizing_error(0.005, 2), ["cx"]
    )
    model.add_all_qubit_readout_error(
        ReadoutError([[0.99, 0.01], [0.01, 0.99]])
    )
    return model


def evaluate_counts(counts, optimum):
    total = sum(counts.values())
    weighted_sum = 0
    optimal_count = 0
    best = 0

    for outcome, count in counts.items():
        bits = outcome.replace(" ", "")[::-1][:NUM_VERTICES]
        value = cut_weight(bits)
        weighted_sum += value * count
        best = max(best, value)

        if value == optimum:
            optimal_count += count

    return (
        weighted_sum / total,
        best,
        optimal_count / total,
    )


def main():
    optimum, _ = find_exact_optimum()
    rng = np.random.default_rng(2026)

    coupling_map = []
    for u, v in PROCESSOR_B_EDGES:
        coupling_map.extend([[u, v], [v, u]])

    ideal_sim = AerSimulator(basis_gates=BASIS_GATES)
    noisy_sim = AerSimulator(
        noise_model=make_noise_model(),
        basis_gates=BASIS_GATES,
    )

    rows = []
    print(f"Exact optimum: {optimum}")

    for p in DEPTHS:
        print(f"\nOptimizing p={p} with {RESTARTS} restarts...")
        best_params = None
        best_expectation = -float("inf")

        for restart in range(RESTARTS):
            initial = np.concatenate([
                rng.uniform(0, 2 * np.pi, p),
                rng.uniform(0, np.pi, p),
            ])

            result = minimize(
                lambda x: -expected_cut(x, p),
                initial,
                method="COBYLA",
                options={"maxiter": MAX_ITERATIONS, "rhobeg": 0.5},
            )

            score = -result.fun
            print(f"  Restart {restart + 1}: {score:.4f}")

            if score > best_expectation:
                best_expectation = score
                best_params = result.x.copy()

        gammas = best_params[:p]
        betas = best_params[p:]

        circuit = make_circuit(gammas, betas, measured=True)
        compiled = transpile(
            circuit,
            basis_gates=BASIS_GATES,
            coupling_map=coupling_map,
            optimization_level=1,
            seed_transpiler=42,
        )

        ideal_values = []
        noisy_values = []
        ideal_probs = []
        noisy_probs = []
        ideal_bests = []
        noisy_bests = []

        for seed in SEEDS:
            ideal_counts = ideal_sim.run(
                compiled, shots=SHOTS, seed_simulator=seed
            ).result().get_counts()

            noisy_counts = noisy_sim.run(
                compiled, shots=SHOTS, seed_simulator=seed
            ).result().get_counts()

            ia, ib, ip = evaluate_counts(ideal_counts, optimum)
            na, nb, np_ = evaluate_counts(noisy_counts, optimum)

            ideal_values.append(ia)
            noisy_values.append(na)
            ideal_bests.append(ib)
            noisy_bests.append(nb)
            ideal_probs.append(ip)
            noisy_probs.append(np_)

        noisy_mean = float(np.mean(noisy_values))
        cx_count = compiled.count_ops().get("cx", 0)
        depth = compiled.depth()

        # Transparent heuristic: reward noisy solution quality,
        # with a modest penalty for two-qubit gate count.
        # This is a project-defined score, not a standard metric.
        cost_penalty = 0.01
        tradeoff_score = noisy_mean - cost_penalty * cx_count

        row = {
            "p": p,
            "best_expected_cut": best_expectation,
            "approximation_ratio": best_expectation / optimum,
            "circuit_depth": depth,
            "cx_count": cx_count,
            "ideal_mean_cut": np.mean(ideal_values),
            "noisy_mean_cut": noisy_mean,
            "noise_gap": np.mean(ideal_values) - noisy_mean,
            "ideal_optimal_probability": np.mean(ideal_probs),
            "noisy_optimal_probability": np.mean(noisy_probs),
            "ideal_mean_best_cut": np.mean(ideal_bests),
            "noisy_mean_best_cut": np.mean(noisy_bests),
            "tradeoff_score": tradeoff_score,
        }
        rows.append(row)

        print(
            f"  Expected={best_expectation:.4f} | "
            f"Noisy mean={noisy_mean:.4f} | "
            f"Depth={depth} | CX={cx_count} | "
            f"Trade-off score={tradeoff_score:.4f}"
        )

    with open("qaoa_tradeoff_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\nFINAL COMPARISON")
    for row in rows:
        print(
            f"p={row['p']} | noisy={row['noisy_mean_cut']:.4f} | "
            f"CX={row['cx_count']} | depth={row['circuit_depth']} | "
            f"score={row['tradeoff_score']:.4f}"
        )

    winner = max(rows, key=lambda r: r["tradeoff_score"])
    print(
        f"\nBest under this chosen score: p={winner['p']}"
    )
    print("Saved: qaoa_tradeoff_results.csv")


if __name__ == "__main__":
    main()
