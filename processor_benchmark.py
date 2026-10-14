
import csv

from qiskit import transpile

from qaoa_solver import (
    NUM_VERTICES,
    P,
    build_qaoa_circuit,
    optimize_qaoa,
)


# ==========================================
# GRAPHCUT-Q: PROCESSOR CONFIGURATION
# ==========================================

SEED = 42
OPTIMIZATION_LEVEL = 1
BASIS_GATES = ["rz", "sx", "x", "cx"]

# Processor A: Updated Challenge Kit, 5-qubit linear chain
PROCESSOR_A = {
    "name": "Processor A",
    "num_qubits": 5,
    "edges": [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
    ],
}

# Processor B: Updated Challenge Kit, 9-qubit sparse topology
PROCESSOR_B = {
    "name": "Processor B",
    "num_qubits": 9,
    "edges": [
        (0, 1),
        (1, 2),
        (2, 3),
        (2, 4),
        (4, 5),
        (5, 6),
        (4, 7),
        (7, 8),
    ],
}


def make_bidirectional(edges):
    """Convert undirected edges into bidirectional CX connections."""
    directed_edges = []

    for u, v in edges:
        directed_edges.append([u, v])
        directed_edges.append([v, u])

    return directed_edges


def circuit_metrics(circuit):
    """Extract basic circuit resource metrics."""
    operations = circuit.count_ops()

    return {
        "qubits": circuit.num_qubits,
        "depth": circuit.depth(),
        "cx_count": operations.get("cx", 0),
        "swap_count": operations.get("swap", 0),
        "single_qubit_count": sum(
            count
            for gate, count in operations.items()
            if gate in ("rz", "sx", "x")
        ),
    }


def benchmark_processor(processor, circuit, logical_cx_count):
    """Compile a circuit for a processor and measure its resources."""
    coupling_map = make_bidirectional(processor["edges"])

    compiled = transpile(
        circuit,
        basis_gates=BASIS_GATES,
        coupling_map=coupling_map,
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED,
    )

    metrics = circuit_metrics(compiled)

    # CX overhead relative to unconstrained compilation.
    # This is NOT an exact SWAP count: routing SWAPs may be
    # decomposed into CX gates during transpilation.
    metrics["extra_cx_vs_logical"] = (
        metrics["cx_count"] - logical_cx_count
    )

    metrics["processor"] = processor["name"]
    metrics["physical_qubits_available"] = processor["num_qubits"]
    metrics["logical_qubits_required"] = NUM_VERTICES
    metrics["coupling_edges"] = len(processor["edges"])

    return compiled, metrics


def main():
    print("=" * 55)
    print("       GRAPHCUT-Q: PROCESSOR BENCHMARK")
    print("=" * 55)

    print("\nOptimizing QAOA parameters...")
    result = optimize_qaoa()
    parameters = result.x

    gammas = parameters[:P]
    betas = parameters[P:]

    # Build the same logical circuit for both architectures.
    logical_circuit = build_qaoa_circuit(gammas, betas)

    # Unconstrained compilation baseline.
    logical_compiled = transpile(
        logical_circuit,
        basis_gates=BASIS_GATES,
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED,
    )

    logical_metrics = circuit_metrics(logical_compiled)
    logical_cx_count = logical_metrics["cx_count"]

    print("\nUNCONSTRAINED BASELINE")
    print("-" * 35)
    print("Logical qubits:", NUM_VERTICES)
    print("Circuit depth:", logical_metrics["depth"])
    print("CX gates:", logical_cx_count)

    all_results = []

    # Processor A capacity check
    print("\nPROCESSOR A")
    print("-" * 35)

    if PROCESSOR_A["num_qubits"] < NUM_VERTICES:
        print("Physical qubits available:", PROCESSOR_A["num_qubits"])
        print("Logical qubits required:", NUM_VERTICES)
        print("Status: FULL CIRCUIT DOES NOT FIT")
        print("No full-size compilation attempted.")
    else:
        compiled_a, metrics_a = benchmark_processor(
            PROCESSOR_A,
            logical_circuit,
            logical_cx_count,
        )
        all_results.append(metrics_a)
        print(metrics_a)

    # Processor B supports the six-qubit problem.
    print("\nPROCESSOR B")
    print("-" * 35)

    compiled_b, metrics_b = benchmark_processor(
        PROCESSOR_B,
        logical_circuit,
        logical_cx_count,
    )
    all_results.append(metrics_b)

    print("Physical qubits available:", PROCESSOR_B["num_qubits"])
    print("Logical qubits required:", NUM_VERTICES)
    print("Circuit depth:", metrics_b["depth"])
    print("CX gates after compilation:", metrics_b["cx_count"])
    print("SWAP gates remaining:", metrics_b["swap_count"])
    print("Extra CX vs unconstrained baseline:",
          metrics_b["extra_cx_vs_logical"])

    # Save compiled B circuit for inspection.
    with open("processor_b_circuit.txt", "w", encoding="utf-8") as file:
        file.write(str(compiled_b.draw(output="text")))

    # Save only metrics that were actually measured.
    if all_results:
        fieldnames = list(all_results[0].keys())

        with open(
            "processor_benchmark_results.csv",
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)

    print("\nSaved files:")
    print("- processor_b_circuit.txt")
    print("- processor_benchmark_results.csv")
    print("\nBenchmark complete.")
    print("=" * 55)


if __name__ == "__main__":
    main()
