
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
    EDGES,
    NUM_VERTICES,
    find_exact_optimum,
)

SHOTS = 4096
SEEDS = [11, 22, 33, 44, 55]

BASIS_GATES = ["rz", "sx", "x", "cx"]

PROCESSOR_B_EDGES = [
    (0, 1), (1, 2), (2, 3), (2, 4),
    (4, 5), (5, 6), (4, 7), (7, 8),
]

NOISE_LEVELS = {
    "Ideal": 0.0,
    "Low (0.5x)": 0.5,
    "Normal (1x)": 1.0,
    "High (2x)": 2.0,
}


def make_coupling_map():
    directed_edges = []

    for u, v in PROCESSOR_B_EDGES:
        directed_edges.extend([[u, v], [v, u]])

    return directed_edges


def create_noise_model(scale):
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

    readout_probability = min(0.01 * scale, 0.5)

    model.add_all_qubit_readout_error(
        ReadoutError([
            [1 - readout_probability, readout_probability],
            [readout_probability, 1 - readout_probability],
        ])
    )

    return model


def evaluate_counts(counts, optimum):
    total_shots = sum(counts.values())
    total_cut = 0
    best_cut = 0
    optimal_count = 0

    for bitstring, count in counts.items():
        bits = bitstring.replace(" ", "")[::-1]

        cut = sum(
            weight
            for u, v, weight in EDGES
            if bits[u] != bits[v]
        )

        total_cut += cut * count
        best_cut = max(best_cut, cut)

        if cut == optimum:
            optimal_count += count

    return {
        "average_cut": total_cut / total_shots,
        "best_cut": best_cut,
        "optimal_probability": optimal_count / total_shots,
    }


def main():
    optimum, _ = find_exact_optimum()

    print("=" * 65)
    print("GRAPHCUT-Q: NOISE SENSITIVITY ANALYSIS")
    print("=" * 65)
    print(f"Exact classical optimum: {optimum}")

    print("\nOptimizing QAOA parameters once...")
    result = optimize_qaoa()
    print(f"Optimizer successful: {result.success}")

    parameters = np.asarray(result.x)
    midpoint = len(parameters) // 2
    gammas = parameters[:midpoint]
    betas = parameters[midpoint:]

    circuit = build_qaoa_circuit(
        gammas,
        betas,
        measurements=True,
    )

    compiled = transpile(
        circuit,
        basis_gates=BASIS_GATES,
        coupling_map=make_coupling_map(),
        optimization_level=1,
        seed_transpiler=42,
    )

    print(f"Compiled circuit depth: {compiled.depth()}")
    print(f"Compiled CX gates: {compiled.count_ops().get('cx', 0)}")

    rows = []

    for label, scale in NOISE_LEVELS.items():
        print(f"\nTesting {label}...")

        simulator = AerSimulator(
            noise_model=create_noise_model(scale),
            basis_gates=BASIS_GATES,
        )

        results = []

        for seed in SEEDS:
            counts = simulator.run(
                compiled,
                shots=SHOTS,
                seed_simulator=seed,
            ).result().get_counts()

            metrics = evaluate_counts(counts, optimum)
            results.append(metrics)

        mean_average = np.mean([
            r["average_cut"] for r in results
        ])

        std_average = np.std([
            r["average_cut"] for r in results
        ], ddof=1)

        mean_optimal_probability = np.mean([
            r["optimal_probability"] for r in results
        ])

        row = {
            "noise_level": label,
            "noise_scale": scale,
            "mean_average_cut": mean_average,
            "std_average_cut": std_average,
            "mean_best_cut": np.mean([
                r["best_cut"] for r in results
            ]),
            "mean_optimal_probability": mean_optimal_probability,
        }

        rows.append(row)

        print(f"Mean average cut: {mean_average:.4f}")
        print(f"Run-to-run standard deviation: {std_average:.4f}")
        print(f"Mean best cut: {row['mean_best_cut']:.2f}")
        print(
            "Mean optimal-cut probability: "
            f"{mean_optimal_probability * 100:.3f}%"
        )

    with open("noise_sensitivity_results.csv", "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 65)
    print("FINAL COMPARISON")
    print("=" * 65)
    print(
        f"{'Noise level':<16}"
        f"{'Mean cut':>12}"
        f"{'Std dev':>12}"
        f"{'Optimal %':>13}"
    )

    for row in rows:
        print(
            f"{row['noise_level']:<16}"
            f"{row['mean_average_cut']:>12.4f}"
            f"{row['std_average_cut']:>12.4f}"
            f"{row['mean_optimal_probability'] * 100:>12.3f}%"
        )

    print("\nSaved: noise_sensitivity_results.csv")


if __name__ == "__main__":
    main()
