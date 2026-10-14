
from itertools import product
import networkx as nx
import matplotlib.pyplot as plt

# GraphCut-Q: fixed development benchmark
NUM_VERTICES = 6

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

def cut_weight(bits):
    """Return the total weight of edges crossing the cut."""
    total = 0

    for u, v, weight in EDGES:
        if bits[u] != bits[v]:
            total += weight

    return total


# Build the graph
G = nx.Graph()
G.add_nodes_from(range(NUM_VERTICES))
G.add_weighted_edges_from(EDGES)

# Exhaustively evaluate all 2^6 assignments
results = []

for bits in product([0, 1], repeat=NUM_VERTICES):
    value = cut_weight(bits)
    results.append((value, bits))

# Find the exact optimum
optimal_value = max(value for value, bits in results)

optimal_solutions = [
    bits for value, bits in results
    if value == optimal_value
]

print("GRAPH CUT-Q: CLASSICAL BASELINE")
print("-" * 35)
print("Vertices:", NUM_VERTICES)
print("Edges:", len(EDGES))
print("Assignments checked:", len(results))
print("Optimal cut weight:", optimal_value)

for bits in optimal_solutions:
    group_a = [i for i, b in enumerate(bits) if b == 0]
    group_b = [i for i, b in enumerate(bits) if b == 1]

    print("Group A:", group_a)
    print("Group B:", group_b)
    print("Bitstring:", "".join(map(str, bits)))
    print()

# Draw the weighted graph
positions = nx.spring_layout(G, seed=42)
edge_labels = nx.get_edge_attributes(G, "weight")

nx.draw(
    G,
    positions,
    with_labels=True,
    node_color="lightblue",
    node_size=900,
    font_weight="bold"
)

nx.draw_networkx_edge_labels(
    G, positions, edge_labels=edge_labels
)

plt.title(f"GraphCut-Q | Exact optimum = {optimal_value}")
plt.tight_layout()
plt.savefig("classical_graph.png", dpi=200)
plt.show()
