
import csv
import numpy as np

from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from qaoa_solver import EDGES, NUM_VERTICES, find_exact_optimum

DEPTHS = [1, 2, 3]
RESTARTS = 3
MAX_ITERATIONS = 150
SHOTS = 4096
SEEDS = [11, 22, 33, 44, 55]
BASIS_GATES = ["rz", "sx", "x", "cx"]

PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]


def cut_weight(bits):
    return sum(
        weight for u, v, weight in EDGES
        if bits[u] != bits[v]
    )


def make_circuit(gammas, betas, measurements=False):
    p = len(gammas)
    qc = QuantumCircuit(NUM_VERTICES)

    qc.h(range(NUM_VERTICES))

    for layer in range(p):
        for u, v, weight in EDGES:
            qc.rzz(-gammas[layer] * weight, u, v)

        for qubit in range(NUM_VERTICES):
            qc.rx(2 * betas[layer], qubit)

    if measurements:
        qc.measure_all()

    return qc


def expected_cut(parameters, p):
    gammas = parameters[:p]
    betas = parameters[p:]

    state = Statevector.from_instruction(
        make_circuit(gammas, betas)
    )

    expectation = 0.0

    for index, probability in enumerate(state.probabilities()):
        bits = format(index, f"0{NUM_VERTICES}b")[::-1]
        expectation += probability * cut_weight(bits)

    return float(expectation)


def make_noise_model(scale=1.0):
    model = NoiseModel()

    if scale == 0:
        return model

    model.add_all_qubit_quantum_error(
        depolarizing_error(0.001 * scale, 1),
        ["rz", "sx", "x"],
    )
    model.add_all_qubit_quantum_error(
        depolarizing_error(0.005 * scale, 2),
        ["cx"],
    )

    readout_p = min(0.01 * scale, 0.5)
    model.add_all_qubit_readout_error(
        ReadoutError([
            [1 - readout_p, readout_p],
            [readout_p, 1 - readout_p],
        ])
    )

    return model


def evaluate_counts(counts, optimum):
    total = sum(counts.values())
    weighted_sum = 0
    best = 0
    optimal_count = 0

    for outcome, count in counts.items():
        bits = outcome.replace(" ", "")[::-1]
        bits = bits[:NUM_VERTICES]
        value = cut_weight(bits)

        weighted_sum += value * count
        best = max(best, value)

        if value == optimum:
            optimal_count += count

    return weighted_sum / total, best, optimal_count / total


def main():
    optimum, _ = find_exact_optimum()
    print("=" * 65)
    print("GRAPHCUT-Q: QAOA DEPTH COMPARISON")
    print("=" * 65)
    print(f"Exact optimum: {optimum}")

    rng = np.random.default_rng(42)
    rows = []

    coupling_map = []
    for u, v in PROCESSOR_B_EDGES:
        coupling_map.extend([[u, v], [v, u]])

    ideal_sim = AerSimulator(basis_gates=BASIS_GATES)
    noisy_sim = AerSimulator(
        noise_model=make_noise_model(1.0),
        basis_gates=BASIS_GATES,
    )

    for p in DEPTHS:
        print(f"\n{'=' * 25} p={p} {'=' * 25}")

        best_parameters = None
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
                options={
                    "maxiter": MAX_ITERATIONS,
                    "rhobeg": 0.5,
                },
            )

            score = -result.fun
            print(
                f"Restart {restart + 1}: "
                f"expected cut={score:.4f}"
            )

            if score > best_expectation:
                best_expectation = score
                best_parameters = result.x.copy()

        gammas = best_parameters[:p]
        betas = best_parameters[p:]

        circuit = make_circuit(
            gammas, betas, measurements=True
        )

        compiled = transpile(
            circuit,
            basis_gates=BASIS_GATES,
            coupling_map=coupling_map,
            optimization_level=1,
            seed_transpiler=42,
        )

        ideal_averages = []
        noisy_averages = []
        ideal_optimal_probs = []
        noisy_optimal_probs = []
        ideal_bests = []
        noisy_bests = []

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

            ia, ib, iprob = evaluate_counts(
                ideal_counts, optimum
            )
            na, nb, nprob = evaluate_counts(
                noisy_counts, optimum
            )

            ideal_averages.append(ia)
            noisy_averages.append(na)
            ideal_bests.append(ib)
            noisy_bests.append(nb)
            ideal_optimal_probs.append(iprob)
            noisy_optimal_probs.append(nprob)

        row = {
            "p": p,
            "best_statevector_expectation": best_expectation,
            "approximation_ratio": best_expectation / optimum,
            "circuit_depth": compiled.depth(),
            "cx_count": compiled.count_ops().get("cx", 0),
            "ideal_mean_cut": np.mean(ideal_averages),
            "noisy_mean_cut": np.mean(noisy_averages),
            "ideal_mean_best_cut": np.mean(ideal_bests),
            "noisy_mean_best_cut": np.mean(noisy_bests),
            "ideal_optimal_probability": np.mean(ideal_optimal_probs),
            "noisy_optimal_probability": np.mean(noisy_optimal_probs),
        }
        rows.append(row)

        print(f"Best expected cut: {best_expectation:.4f}")
        print(f"Approximation ratio: {best_expectation / optimum:.4f}")
        print(f"Compiled depth: {compiled.depth()}")
        print(f"Compiled CX count: {row['cx_count']}")
        print(f"Ideal sampled mean: {row['ideal_mean_cut']:.4f}")
        print(f"Noisy sampled mean: {row['noisy_mean_cut']:.4f}")
        print(
            "Noisy optimal probability: "
            f"{row['noisy_optimal_probability'] * 100:.3f}%"
        )

    with open("qaoa_depth_results.csv", "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 65)
    print("FINAL SUMMARY")
    print("=" * 65)

    for row in rows:
        print(
            f"p={row['p']} | "
            f"Expected={row['best_statevector_expectation']:.3f} | "
            f"Ratio={row['approximation_ratio']:.3f} | "
            f"Depth={row['circuit_depth']} | "
            f"CX={row['cx_count']} | "
            f"Noisy mean={row['noisy_mean_cut']:.3f}"
        )

    print("\nSaved: qaoa_depth_results.csv")


if __name__ == "__main__":
    main()
