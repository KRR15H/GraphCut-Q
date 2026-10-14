"""
GraphCut-Q: Processor D architecture benchmark
Compatible with Qiskit 2.x (including 2.5.2).

Run from the GraphCut-Q project root:
    python processor_d_benchmark.py

This script compares:
- Unconstrained compilation baseline
- Processor B: existing 9-qubit sparse topology
- Processor D: proposed 6-qubit fully connected topology

It uses the same graph, QAOA solver, and optimized parameters for B and D.
Processor A is omitted from compilation because its 5 qubits cannot host the
full 6-qubit logical circuit without a separate encoding/embedding strategy.
"""

import csv
from qiskit import transpile

from qaoa_solver import (
    NUM_VERTICES,
    P,
    build_qaoa_circuit,
    optimize_qaoa,
)

SEED = 42
OPTIMIZATION_LEVEL = 1
BASIS_GATES = ["rz", "sx", "x", "cx"]

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

# Proposed custom architecture: six fully connected physical qubits.
# This is a design proposal; the benchmark measures its compilation cost,
# not the feasibility/cost of manufacturing such hardware.
PROCESSOR_D = {
    "name": "Processor D",
    "num_qubits": 6,
    "edges": [
        (u, v)
        for u in range(NUM_VERTICES)
        for v in range(u + 1, NUM_VERTICES)
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
    """Extract comparable compiled-circuit resource metrics."""
    operations = circuit.count_ops()
    return {
        "qubits": circuit.num_qubits,
        "depth": circuit.depth(),
        "cx_count": int(operations.get("cx", 0)),
        "swap_count_remaining": int(operations.get("swap", 0)),
        "single_qubit_count": int(sum(
            count
            for gate, count in operations.items()
            if gate in ("rz", "sx", "x")
        )),
    }


def compile_for_processor(processor, circuit, logical_cx_count):
    """Transpile for one coupling map and return circuit plus metrics."""
    compiled = transpile(
        circuit,
        basis_gates=BASIS_GATES,
        coupling_map=make_bidirectional(processor["edges"]),
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED,
    )
    metrics = circuit_metrics(compiled)
    metrics.update({
        "processor": processor["name"],
        "physical_qubits_available": processor["num_qubits"],
        "logical_qubits_required": NUM_VERTICES,
        "coupling_edges": len(processor["edges"]),
        "extra_cx_vs_unconstrained": metrics["cx_count"] - logical_cx_count,
    })
    return compiled, metrics


def main():
    print("=" * 64)
    print("GRAPHCUT-Q: PROCESSOR B vs CUSTOM PROCESSOR D")
    print("=" * 64)

    if PROCESSOR_D["num_qubits"] < NUM_VERTICES:
        raise ValueError("Processor D has fewer physical qubits than the logical problem.")

    print("\nOptimizing QAOA parameters once for a fair comparison...")
    result = optimize_qaoa()
    parameters = result.x
    gammas = parameters[:P]
    betas = parameters[P:]
    logical_circuit = build_qaoa_circuit(gammas, betas)

    baseline = transpile(
        logical_circuit,
        basis_gates=BASIS_GATES,
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED,
    )
    baseline_metrics = circuit_metrics(baseline)
    logical_cx_count = baseline_metrics["cx_count"]

    print("\nUNCONSTRAINED BASELINE")
    print(f"  Logical qubits: {NUM_VERTICES}")
    print(f"  Depth: {baseline_metrics['depth']}")
    print(f"  CX count: {logical_cx_count}")

    results = []
    compiled_circuits = {}

    for processor in (PROCESSOR_B, PROCESSOR_D):
        compiled, metrics = compile_for_processor(
            processor, logical_circuit, logical_cx_count
        )
        compiled_circuits[processor["name"]] = compiled
        results.append(metrics)

        print(f"\n{processor['name'].upper()}")
        print("-" * 40)
        print(f"  Physical qubits available: {processor['num_qubits']}")
        print(f"  Coupling edges: {len(processor['edges'])}")
        print(f"  Depth: {metrics['depth']}")
        print(f"  CX gates: {metrics['cx_count']}")
        print(f"  SWAP gates remaining after transpilation: {metrics['swap_count_remaining']}")
        print(f"  Single-qubit gates: {metrics['single_qubit_count']}")
        print(f"  Extra CX vs unconstrained baseline: {metrics['extra_cx_vs_unconstrained']}")

    with open("processor_d_comparison_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    with open("processor_b_circuit_comparison.txt", "w", encoding="utf-8") as f:
        f.write(str(compiled_circuits["Processor B"].draw(output="text")))

    with open("processor_d_circuit.txt", "w", encoding="utf-8") as f:
        f.write(str(compiled_circuits["Processor D"].draw(output="text")))

    print("\nSaved files:")
    print("  processor_d_comparison_results.csv")
    print("  processor_b_circuit_comparison.txt")
    print("  processor_d_circuit.txt")
    print("\nInterpretation note:")
    print("  A remaining SWAP count of zero does not prove that routing was unnecessary.")
    print("  Compare CX overhead against the unconstrained baseline as well.")
    print("  Processor D is a proposed topology; this is a simulated compilation comparison.")
    print("=" * 64)


if __name__ == "__main__":
    main()
