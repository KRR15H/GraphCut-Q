
from qiskit import transpile
from qiskit_aer import AerSimulator

from qaoa_solver import (
    P,
    NUM_VERTICES,
    EDGES,
    best_parameters,
    build_qaoa_circuit,
    cut_weight,
    find_exact_optimum,
    optimize_qaoa,
)

# ==========================================
# CONFIGURATION
# ==========================================

SHOTS = 4096
RANDOM_SEED = 42


# ==========================================
# MEASUREMENT SIMULATOR
# ==========================================

def main():
    print("=" * 50)
    print("    GRAPHCUT-Q: MEASUREMENT SIMULATOR")
    print("=" * 50)

    # Find the exact classical optimum
    exact_optimum, _ = find_exact_optimum()
    print("Exact classical optimum:", exact_optimum)

    # Optimize parameters now; no previous run is required
    print("\nOptimizing QAOA parameters...")
    optimization_result = optimize_qaoa()
    parameters = optimization_result.x

    gammas = parameters[:P]
    betas = parameters[P:]

    print("Optimized gamma:", gammas)
    print("Optimized beta:", betas)

    # Build circuit with measurements
    circuit = build_qaoa_circuit(
        gammas,
        betas,
        measurements=True,
    )

    # Configure the simulator
    simulator = AerSimulator()

    compiled_circuit = transpile(
        circuit,
        simulator,
        seed_transpiler=RANDOM_SEED,
    )

    # Run measurement shots
    print(f"\nRunning {SHOTS} shots...")

    job = simulator.run(
        compiled_circuit,
        shots=SHOTS,
        seed_simulator=RANDOM_SEED,
    )

    counts = job.result().get_counts()

    # Calculate measured cut statistics
    weighted_total = 0
    best_observed_cut = -1
    best_observed_bitstrings = []

    for bitstring, frequency in counts.items():
        # Qiskit displays qubit 0 at the right
        bits = tuple(int(bit) for bit in reversed(bitstring))
        value = cut_weight(bits)

        weighted_total += value * frequency

        if value > best_observed_cut:
            best_observed_cut = value
            best_observed_bitstrings = [bitstring]
        elif value == best_observed_cut:
            best_observed_bitstrings.append(bitstring)

    average_cut = weighted_total / SHOTS

    # Probability of measuring an optimal cut
    optimal_shots = 0

    for bitstring, frequency in counts.items():
        bits = tuple(int(bit) for bit in reversed(bitstring))

        if cut_weight(bits) == exact_optimum:
            optimal_shots += frequency

    optimal_probability = optimal_shots / SHOTS

    # ==========================================
    # DISPLAY RESULTS
    # ==========================================

    print("\n" + "=" * 50)
    print("             FINAL RESULTS")
    print("=" * 50)

    print("Vertices:", NUM_VERTICES)
    print("Edges:", len(EDGES))
    print("QAOA depth:", P)
    print("Measurement shots:", SHOTS)
    print("Distinct bitstrings:", len(counts))
    print("Exact classical optimum:", exact_optimum)
    print("Best cut observed:", best_observed_cut)
    print(f"Average measured cut: {average_cut:.4f}")
    print(f"Optimal-cut probability: {optimal_probability:.2%}")

    print("\nMost frequent outcomes:")

    top_outcomes = sorted(
        counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    for bitstring, frequency in top_outcomes:
        bits = tuple(int(bit) for bit in reversed(bitstring))
        value = cut_weight(bits)

        print(
            f"Bitstring: {bitstring} | "
            f"Cut weight: {value:2d} | "
            f"Count: {frequency:4d} | "
            f"Probability: {frequency / SHOTS:.2%}"
        )

    print("\nBest observed bitstrings:")

    for bitstring in best_observed_bitstrings:
        print(bitstring)

    print("=" * 50)


if __name__ == "__main__":
    main()
