
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    depolarizing_error,
    ReadoutError,
)

from qaoa_solver import (
    P,
    NUM_VERTICES,
    build_qaoa_circuit,
    optimize_qaoa,
    cut_weight,
    find_exact_optimum,
)


# ==========================================
# CONFIGURATION
# ==========================================

SHOTS = 4096
SEED = 42

BASIS_GATES = ["rz", "sx", "x", "cx"]

# Processor B topology from the Updated Challenge Kit
PROCESSOR_B_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (2, 4),
    (4, 5),
    (5, 6),
    (4, 7),
    (7, 8),
]

SINGLE_QUBIT_NOISE = 0.001
CX_NOISE = 0.005
READOUT_NOISE = 0.01


def make_coupling_map():
    """Return bidirectional connections for Processor B."""
    directed_edges = []

    for u, v in PROCESSOR_B_EDGES:
        directed_edges.append([u, v])
        directed_edges.append([v, u])

    return directed_edges


def create_noise_model():
    """Create the challenge's specified synthetic noise model."""
    noise_model = NoiseModel()

    one_qubit_error = depolarizing_error(
        SINGLE_QUBIT_NOISE, 1
    )

    two_qubit_error = depolarizing_error(
        CX_NOISE, 2
    )

    readout_error = ReadoutError([
        [1 - READOUT_NOISE, READOUT_NOISE],
        [READOUT_NOISE, 1 - READOUT_NOISE],
    ])

    # Apply one-qubit errors to each supported one-qubit gate.
    noise_model.add_all_qubit_quantum_error(
        one_qubit_error,
        ["rz", "sx", "x"],
    )

    # Apply two-qubit errors to CX gates.
    noise_model.add_all_qubit_quantum_error(
        two_qubit_error,
        ["cx"],
    )

    # Apply readout errors to measured qubits.
    noise_model.add_all_qubit_readout_error(readout_error)

    return noise_model


def evaluate_counts(counts):
    """Calculate objective statistics from measured bitstrings."""
    total_shots = sum(counts.values())
    total_weight = 0
    best_cut = 0
    optimal_shots = 0

    exact_optimum, _ = find_exact_optimum()

    for bitstring, frequency in counts.items():
        # Classical register ordering: qubit 0 is on the right.
        bits = tuple(
            int(bit) for bit in reversed(bitstring.replace(" ", ""))
        )

        if len(bits) != NUM_VERTICES:
            raise ValueError(
                f"Expected {NUM_VERTICES} measured bits, "
                f"received {len(bits)} in {bitstring!r}."
            )

        value = cut_weight(bits)

        total_weight += value * frequency
        best_cut = max(best_cut, value)

        if value == exact_optimum:
            optimal_shots += frequency

    return {
        "average_cut": total_weight / total_shots,
        "best_observed_cut": best_cut,
        "optimal_probability": optimal_shots / total_shots,
        "distinct_bitstrings": len(counts),
    }


def run_simulation(simulator, compiled_circuit):
    """Execute the compiled circuit and return its counts."""
    job = simulator.run(
        compiled_circuit,
        shots=SHOTS,
        seed_simulator=SEED,
    )

    return job.result().get_counts()


def main():
    print("=" * 55)
    print("       GRAPHCUT-Q: IDEAL VS NOISY")
    print("=" * 55)

    exact_optimum, _ = find_exact_optimum()
    print("Exact classical optimum:", exact_optimum)

    # Optimize parameters using the ideal objective.
    print("\nOptimizing QAOA parameters...")
    optimization_result = optimize_qaoa()

    parameters = optimization_result.x
    gammas = parameters[:P]
    betas = parameters[P:]

    print("Parameters optimized:", optimization_result.success)

    # Add measurements before transpiling.
    circuit = build_qaoa_circuit(
        gammas,
        betas,
        measurements=True,
    )

    # Compile once so ideal and noisy results use the same circuit.
    compiled = transpile(
        circuit,
        basis_gates=BASIS_GATES,
        coupling_map=make_coupling_map(),
        optimization_level=1,
        seed_transpiler=SEED,
    )

    print("\nCompiled Processor B circuit")
    print("Qubits in compiled circuit:", compiled.num_qubits)
    print("Circuit depth:", compiled.depth())
    print("CX count:", compiled.count_ops().get("cx", 0))
    print("Shots per experiment:", SHOTS)

    # Ideal simulation
    print("\nRunning ideal simulation...")
    ideal_simulator = AerSimulator(
        basis_gates=BASIS_GATES
    )
    ideal_counts = run_simulation(ideal_simulator, compiled)
    ideal_results = evaluate_counts(ideal_counts)

    # Noisy simulation
    print("Running noisy simulation...")
    noise_model = create_noise_model()

    noisy_simulator = AerSimulator(
        noise_model=noise_model,
        basis_gates=BASIS_GATES,
    )

    noisy_counts = run_simulation(noisy_simulator, compiled)
    noisy_results = evaluate_counts(noisy_counts)

    # Report results
    print("\n" + "=" * 55)
    print("                 RESULTS")
    print("=" * 55)

    for label, results in [
        ("IDEAL", ideal_results),
        ("NOISY", noisy_results),
    ]:
        print(f"\n{label} SIMULATION")
        print("-" * 35)
        print(f"Average cut: {results['average_cut']:.4f}")
        print(f"Best observed cut: {results['best_observed_cut']}")
        print(
            f"Optimal-cut probability: "
            f"{results['optimal_probability']:.2%}"
        )
        print(
            f"Distinct bitstrings: "
            f"{results['distinct_bitstrings']}"
        )

    print("\nNOISE IMPACT")
    print("-" * 35)
    print(
        "Change in average cut:",
        f"{noisy_results['average_cut'] - ideal_results['average_cut']:.4f}",
    )
    print(
        "Change in optimal-cut probability:",
        f"{noisy_results['optimal_probability'] - ideal_results['optimal_probability']:.2%}",
    )

    print("\nBenchmark complete.")
    print("=" * 55)


if __name__ == "__main__":
    main()
