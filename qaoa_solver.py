
from itertools import product

import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


# ==========================================
# GRAPHCUT-Q: CONFIGURATION
# ==========================================

NUM_VERTICES = 6
P = 1  # QAOA depth

EDGES = [
    (0, 1, 3),
    (0, 2, 2),
    (0, 3, 4),
    (1, 2, 5),
    (1, 4, 2),
    (1, 5, 3),
    (2, 3, 1),
    (2, 4, 4),
    (3, 5, 5),
    (4, 5, 2),
]

MAX_ITERATIONS = 200
RANDOM_SEED = 42


# ==========================================
# CLASSICAL CUT EVALUATION
# ==========================================

def cut_weight(bits):
    """Return the total weight of edges crossing a cut."""
    return sum(
        weight
        for u, v, weight in EDGES
        if bits[u] != bits[v]
    )


def find_exact_optimum():
    """Find the exact optimum by enumerating all bitstrings."""
    all_cuts = [
        (cut_weight(bits), bits)
        for bits in product([0, 1], repeat=NUM_VERTICES)
    ]

    optimum = max(value for value, bits in all_cuts)

    optimal_solutions = [
        bits
        for value, bits in all_cuts
        if value == optimum
    ]

    return optimum, optimal_solutions


# ==========================================
# QAOA CIRCUIT
# ==========================================

def build_qaoa_circuit(gammas, betas, measurements=False):
    """
    Construct a weighted Max-Cut QAOA circuit.

    gammas and betas each contain P parameters.
    Measurements are optional.
    """
    if len(gammas) != P or len(betas) != P:
        raise ValueError(f"Expected exactly {P} gamma and beta values.")

    qc = QuantumCircuit(NUM_VERTICES)

    # Initial equal superposition
    qc.h(range(NUM_VERTICES))

    for layer in range(P):
        gamma = float(gammas[layer])
        beta = float(betas[layer])

        # Cost layer
        for u, v, weight in EDGES:
            qc.rzz(-gamma * weight, u, v)

        # Mixer layer
        for qubit in range(NUM_VERTICES):
            qc.rx(2 * beta, qubit)

    if measurements:
        qc.measure_all()

    return qc


# ==========================================
# IDEAL EXPECTATION VALUE
# ==========================================

def expected_cut(parameters):
    """Calculate the expected cut with an ideal statevector."""
    gammas = parameters[:P]
    betas = parameters[P:]

    circuit = build_qaoa_circuit(gammas, betas)
    probabilities = Statevector.from_instruction(
        circuit
    ).probabilities_dict()

    expectation = 0.0

    for bitstring, probability in probabilities.items():
        # Qiskit bitstrings place qubit 0 on the right
        bits = tuple(int(bit) for bit in reversed(bitstring))
        expectation += probability * cut_weight(bits)

    return float(expectation)


def objective(parameters):
    """SciPy minimizes; negate the value to maximize the cut."""
    return -expected_cut(parameters)


# ==========================================
# PARAMETER OPTIMIZATION
# ==========================================

def optimize_qaoa():
    """Optimize QAOA angles and return the result."""
    rng = np.random.default_rng(RANDOM_SEED)

    initial_parameters = np.concatenate([
        rng.uniform(0, 2 * np.pi, P),
        rng.uniform(0, np.pi, P),
    ])

    result = minimize(
        objective,
        initial_parameters,
        method="COBYLA",
        options={
            "maxiter": MAX_ITERATIONS,
            "rhobeg": 0.5,
        },
    )

    return result


# ==========================================
# RESULTS
# ==========================================

def main():
    global best_parameters

    exact_optimum, optimal_solutions = find_exact_optimum()

    print("=" * 48)
    print("          GRAPHCUT-Q: QAOA RESULTS")
    print("=" * 48)

    print(f"Vertices: {NUM_VERTICES}")
    print(f"Edges: {len(EDGES)}")
    print(f"Assignments checked: {2 ** NUM_VERTICES}")
    print(f"QAOA depth (p): {P}")
    print(f"Exact classical optimum: {exact_optimum}")

    result = optimize_qaoa()

    # Store optimized angles for other modules to use
    best_parameters = np.asarray(result.x, dtype=float)

    best_expected_cut = expected_cut(best_parameters)
    approximation_ratio = best_expected_cut / exact_optimum

    print(f"QAOA expected cut: {best_expected_cut:.4f}")
    print(f"Approximation ratio: {approximation_ratio:.4f}")
    print("Optimized gamma:", best_parameters[:P])
    print("Optimized beta:", best_parameters[P:])
    print("Optimizer success:", result.success)
    print("Optimizer message:", result.message)

    print("\nOne exact optimal bitstring:")
    print("".join(map(str, optimal_solutions[0])))

    print("=" * 48)

    return best_parameters


# This gets populated when the optimization function is called.
best_parameters = None


if __name__ == "__main__":
    main()
