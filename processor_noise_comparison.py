"""
GraphCut-Q: noisy performance comparison for Processor B vs Processor D.

Run from the GraphCut-Q project root:
    python processor_noise_comparison.py

Uses the same logical graph, optimized QAOA parameters, shot count, and noise
rates for both architectures. Runs several independent sampling seeds.

Notes:
- Processor D is a proposed fully connected 6-qubit topology.
- This is a simulator-based comparison, not a claim about real hardware.
- The script uses Qiskit Aer; install qiskit-aer if needed.
"""

import csv
import math
from pathlib import Path

import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from qaoa_solver import (
    NUM_VERTICES,
    P,
    build_qaoa_circuit,
    optimize_qaoa,
    cut_weight,
    find_exact_optimum,
)

SEED_TRANSPILER = 42
OPTIMIZATION_LEVEL = 1
BASIS_GATES = ["rz", "sx", "x", "cx"]
SHOTS = 4096
REPEAT_SEEDS = list(range(2001, 2011))  # 10 repeated runs per architecture

P_SINGLE_QUBIT = 0.001
P_CX = 0.005
P_READOUT = 0.01

PROCESSORS = [
    {
        "name": "Processor B",
        "num_qubits": 9,
        "edges": [
            (0, 1), (1, 2), (2, 3), (2, 4),
            (4, 5), (5, 6), (4, 7), (7, 8),
        ],
    },
    {
        "name": "Processor D",
        "num_qubits": 6,
        "edges": [
            (u, v)
            for u in range(NUM_VERTICES)
            for v in range(u + 1, NUM_VERTICES)
        ],
    },
]


def bidirectional(edges):
    return [[u, v] for u, v in edges] + [[v, u] for u, v in edges]


def make_noise_model():
    noise = NoiseModel()
    one_qubit_error = depolarizing_error(P_SINGLE_QUBIT, 1)
    cx_error = depolarizing_error(P_CX, 2)
    readout_error = ReadoutError([
        [1 - P_READOUT, P_READOUT],
        [P_READOUT, 1 - P_READOUT],
    ])

    noise.add_all_qubit_quantum_error(one_qubit_error, ["sx", "x"])
    noise.add_all_qubit_quantum_error(cx_error, ["cx"])
    # RZ is ideal in this model, as it is commonly treated as a virtual gate.
    noise.add_all_qubit_readout_error(readout_error)
    return noise


def measured_cut_stats(counts, optimal_weight):
    total_shots = sum(counts.values())
    weighted_sum = 0.0
    best_sampled = 0
    optimal_count = 0

    for bitstring, count in counts.items():
        # Qiskit count strings list classical bit c[n-1] first; reversing
        # gives the logical order expected by cut_weight(bits).
        bits = [int(bit) for bit in bitstring.replace(" ", "")[::-1]]
        weight = cut_weight(bits)
        weighted_sum += weight * count
        best_sampled = max(best_sampled, weight)
        if weight == optimal_weight:
            optimal_count += count

    return {
        "mean_cut": weighted_sum / total_shots,
        "best_sampled_cut": best_sampled,
        "optimal_cut_probability": optimal_count / total_shots,
    }


def mean_ci95(values):
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    if len(values) < 2:
        return mean, 0.0, mean, mean
    sd = float(np.std(values, ddof=1))
    half_width = 1.96 * sd / math.sqrt(len(values))
    return mean, sd, mean - half_width, mean + half_width


def main():
    print("=" * 68)
    print("GRAPHCUT-Q: NOISY PROCESSOR B vs PROCESSOR D")
    print("=" * 68)
    print(f"Shots per run: {SHOTS}")
    print(f"Repeated seeds: {REPEAT_SEEDS[0]}..{REPEAT_SEEDS[-1]} ({len(REPEAT_SEEDS)} runs)")
    print(f"Noise: 1Q={P_SINGLE_QUBIT}, CX={P_CX}, readout={P_READOUT}")

    print("\\nFinding exact classical optimum...")
    exact_result = find_exact_optimum()

    # qaoa_solver.py in this project returns (best_weight, optimal_bitstrings).
    # Normalize explicitly so the script is robust to the return order seen locally.
    if isinstance(exact_result[0], (int, float, np.integer, np.floating)):
        optimum_weight = float(exact_result[0])
        optimal_bitstrings = exact_result[1]
    else:
        optimal_bitstrings = exact_result[0]
        optimum_weight = float(exact_result[1])

    # Normalize a single bitstring vs a list of bitstrings.
    if optimal_bitstrings and isinstance(optimal_bitstrings[0], (int, np.integer)):
        optimal_bitstrings = [optimal_bitstrings]

    print(f"Exact optimum cut weight: {optimum_weight:g}")
    if optimal_bitstrings:
        print(f"One optimal bitstring: {''.join(map(str, optimal_bitstrings[0]))}")
    else:
        raise RuntimeError("find_exact_optimum() returned no optimal bitstrings.")

    print("\nOptimizing QAOA parameters once...")
    opt_result = optimize_qaoa()
    parameters = opt_result.x
    gammas = parameters[:P]
    betas = parameters[P:]
    logical_circuit = build_qaoa_circuit(gammas, betas, measurements=True)

    noise_model = make_noise_model()
    simulator = AerSimulator(noise_model=noise_model, basis_gates=BASIS_GATES)

    all_rows = []
    summary_rows = []

    for processor in PROCESSORS:
        print(f"\n--- {processor['name']} ---")
        compiled = transpile(
            logical_circuit,
            basis_gates=BASIS_GATES,
            coupling_map=bidirectional(processor["edges"]),
            optimization_level=OPTIMIZATION_LEVEL,
            seed_transpiler=SEED_TRANSPILER,
        )

        ops = compiled.count_ops()
        print(f"Physical qubits available: {processor['num_qubits']}")
        print(f"Compiled depth: {compiled.depth()}")
        print(f"Compiled CX count: {ops.get('cx', 0)}")

        run_means = []
        run_opt_probs = []
        run_best = []

        for seed in REPEAT_SEEDS:
            job = simulator.run(compiled, shots=SHOTS, seed_simulator=seed)
            counts = job.result().get_counts()
            stats = measured_cut_stats(counts, optimum_weight)
            row = {
                "processor": processor["name"],
                "seed": seed,
                "shots": SHOTS,
                "compiled_depth": compiled.depth(),
                "cx_count": int(ops.get("cx", 0)),
                "swap_count_remaining": int(ops.get("swap", 0)),
                "mean_cut": stats["mean_cut"],
                "best_sampled_cut": stats["best_sampled_cut"],
                "optimal_cut_probability": stats["optimal_cut_probability"],
            }
            all_rows.append(row)
            run_means.append(stats["mean_cut"])
            run_opt_probs.append(stats["optimal_cut_probability"])
            run_best.append(stats["best_sampled_cut"])
            print(
                f"seed={seed}: mean cut={stats['mean_cut']:.4f}, "
                f"best={stats['best_sampled_cut']}, "
                f"optimal probability={stats['optimal_cut_probability']:.3%}"
            )

        mean_cut, sd_cut, ci_low, ci_high = mean_ci95(run_means)
        mean_prob, sd_prob, prob_low, prob_high = mean_ci95(run_opt_probs)
        summary = {
            "processor": processor["name"],
            "num_physical_qubits": processor["num_qubits"],
            "coupling_edges": len(processor["edges"]),
            "shots_per_run": SHOTS,
            "num_repeats": len(REPEAT_SEEDS),
            "compiled_depth": compiled.depth(),
            "cx_count": int(ops.get("cx", 0)),
            "mean_cut_across_runs": mean_cut,
            "sd_of_run_mean_cuts": sd_cut,
            "mean_cut_ci95_low": ci_low,
            "mean_cut_ci95_high": ci_high,
            "mean_optimal_cut_probability": mean_prob,
            "sd_optimal_cut_probability": sd_prob,
            "optimal_prob_ci95_low": prob_low,
            "optimal_prob_ci95_high": prob_high,
            "mean_best_sampled_cut": float(np.mean(run_best)),
        }
        summary_rows.append(summary)

        print(
            f"SUMMARY: mean cut={mean_cut:.4f} "
            f"(95% CI {ci_low:.4f} to {ci_high:.4f}); "
            f"mean optimal probability={mean_prob:.3%}"
        )

    with open("processor_noise_comparison_runs.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    with open("processor_noise_comparison_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nSaved:")
    print("  processor_noise_comparison_runs.csv")
    print("  processor_noise_comparison_summary.csv")
    print("\nCompare the confidence intervals and cut metrics; do not infer a winner")
    print("from circuit depth alone.")
    print("=" * 68)


if __name__ == "__main__":
    main()
