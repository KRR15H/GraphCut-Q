
import csv
import numpy as np

from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    depolarizing_error,
    ReadoutError,
)

from qaoa_solver import (
    build_qaoa_circuit,
    optimize_qaoa,
    cut_weight,
    find_exact_optimum,
)

SHOTS = 4096
SEEDS = [11, 22, 33, 44, 55]

BASIS_GATES = ["rz", "sx", "x", "cx"]

PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]


def create_noise_model():
    noise_model = NoiseModel()

    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(0.001, 1),
        ["rz", "sx", "x"],
    )

    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(0.005, 2),
        ["cx"],
    )

    readout_error = ReadoutError([
        [0.99, 0.01],
        [0.01, 0.99],
    ])

    noise_model.add_all_qubit_readout_error(readout_error)

    return noise_model


def make_coupling_map():
    edges = []

    for u, v in PROCESSOR_B_EDGES:
        edges.append([u, v])
        edges.append([v, u])

    return edges


def evaluate_counts(counts, num_vertices, edges):
    total_shots = sum(counts.values())
    total_cut = 0
    best_cut = 0
    optimal_count = 0

    for bitstring, count in counts.items():
        bits = bitstring.replace(" ", "")[::-1]
        bits = bits[:num_vertices]

        cut = sum(
            weight
            for u, v, weight in edges
            if bits[u] != bits[v]
        )

        total_cut += cut * count
        best_cut = max(best_cut, cut)

        if cut == 27:
            optimal_count += count

    return {
        "average_cut": total_cut / total_shots,
        "best_cut": best_cut,
        "optimal_probability": optimal_count / total_shots,
    }


def main():
    optimum, _ = find_exact_optimum()

    print("=" * 60)
    print("GRAPHCUT-Q: REPEATED-SEED BENCHMARK")
    print("=" * 60)
    print(f"Exact optimum: {optimum}")

    print("\nOptimizing QAOA parameters once...")
    result = optimize_qaoa()
    print(f"Optimization successful: {result.success}")

    parameters = np.asarray(result.x)
    gammas = parameters[:len(parameters) // 2]
    betas = parameters[len(parameters) // 2:]

    measured_circuit = build_qaoa_circuit(
        gammas, betas, measurements=True
    )

    compiled_circuit = transpile(
        measured_circuit,
        basis_gates=BASIS_GATES,
        coupling_map=make_coupling_map(),
        optimization_level=1,
        seed_transpiler=42,
    )

    ideal_simulator = AerSimulator(basis_gates=BASIS_GATES)
    noisy_simulator = AerSimulator(
        noise_model=create_noise_model(),
        basis_gates=BASIS_GATES,
    )

    rows = []

    print("\nRunning experiments...")
    print("-" * 60)

    for seed in SEEDS:
        ideal_counts = ideal_simulator.run(
            compiled_circuit,
            shots=SHOTS,
            seed_simulator=seed,
        ).result().get_counts()

        noisy_counts = noisy_simulator.run(
            compiled_circuit,
            shots=SHOTS,
            seed_simulator=seed,
        ).result().get_counts()

        ideal = evaluate_counts(
            ideal_counts,
            6,
            __import__("qaoa_solver").EDGES,
        )

        noisy = evaluate_counts(
            noisy_counts,
            6,
            __import__("qaoa_solver").EDGES,
        )

        row = {
            "seed": seed,
            "ideal_average_cut": ideal["average_cut"],
            "noisy_average_cut": noisy["average_cut"],
            "average_cut_change": (
                noisy["average_cut"] - ideal["average_cut"]
            ),
            "ideal_best_cut": ideal["best_cut"],
            "noisy_best_cut": noisy["best_cut"],
            "ideal_optimal_probability": ideal["optimal_probability"],
            "noisy_optimal_probability": noisy["optimal_probability"],
        }

        rows.append(row)

        print(
            f"Seed {seed}: "
            f"Ideal avg={ideal['average_cut']:.4f}, "
            f"Noisy avg={noisy['average_cut']:.4f}, "
            f"Change={row['average_cut_change']:+.4f}"
        )

    output_file = "repeated_benchmark_results.csv"

    with open(output_file, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    changes = [
        row["average_cut_change"] for row in rows
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Experiments: {len(SEEDS)}")
    print(f"Shots per experiment: {SHOTS}")
    print(f"Mean noisy-minus-ideal change: {np.mean(changes):+.4f}")
    print(f"Standard deviation of changes: {np.std(changes, ddof=1):.4f}")
    print(f"Saved results to: {output_file}")


if __name__ == "__main__":
    main()
