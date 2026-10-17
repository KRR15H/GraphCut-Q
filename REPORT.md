# GraphCut-Q: A Hardware-Aware QAOA Study for Weighted Max-Cut

**Event:** Qiskit Fall Fest 2026 — Quantum Optimization Track  
**Problem:** PS-O1 — Max-Cut on a Weighted Graph  
**Repository:** https://github.com/KRR15H/GraphCut-Q  
**Primary implementation:** Python, Qiskit  
**Report status:** Experimental results and simulation study

---

## Abstract

GraphCut-Q studies the weighted Max-Cut problem using the Quantum Approximate Optimization Algorithm (QAOA), with an exact classical solver used as a reference. The project evaluates solution quality alongside circuit cost and simulated noise effects. It also compares the same logical problem across two processor-topology models: a sparse, heavy-hex-inspired Processor B and a fully connected, custom Processor D.

The fixed instance contains six vertices and ten weighted edges. Exhaustive classical search finds an optimal cut weight of **27**. In an initial QAOA \(p=1\) run, the expected cut weight was **16.9644**, corresponding to an approximation ratio of **0.6283**. Additional depth and noise experiments show the trade-off between deeper circuits, solution quality, and hardware-related costs. Processor D is a **simulated custom topology**, not a claim of execution on a physical quantum processor.

## 1. Problem Statement

Given a weighted undirected graph \(G=(V,E)\), Max-Cut partitions the vertices into two sets so that the total weight of edges crossing between the sets is maximized.

Let \(x_i\in\{0,1\}\) denote the partition assigned to vertex \(i\). An edge \((i,j)\) contributes its weight \(w_{ij}\) when \(x_i\ne x_j\). The objective is

\[
C(x)=\sum_{(i,j)\in E} w_{ij}\,[x_i\ne x_j].
\]

The project aims to:

1. Formulate the weighted Max-Cut objective for QAOA.
2. Establish an exact classical reference solution.
3. Optimize and evaluate QAOA at multiple circuit depths.
4. Compare circuit resource requirements under different coupling topologies.
5. Study the impact of a specified noise model on solution quality.
6. Keep the graph instance fixed across processor comparisons.

## 2. Graph Instance

The experiments use a fixed graph with six vertices and ten weighted edges. Edge weights are integers from 1 to 5.

| Edge | Weight |
|---|---:|
| (0, 1) | 3 |
| (0, 2) | 2 |
| (0, 3) | 4 |
| (1, 2) | 5 |
| (1, 4) | 2 |
| (1, 5) | 3 |
| (2, 3) | 1 |
| (2, 4) | 4 |
| (3, 5) | 5 |
| (4, 5) | 2 |

The instance is held fixed for the classical baseline and the reported QAOA and topology experiments, allowing comparisons without changing the optimization problem.

## 3. Classical Baseline

Because the graph has six vertices, there are \(2^6=64\) possible binary assignments. The classical baseline exhaustively evaluates these assignments and selects the maximum cut weight.

| Metric | Result |
|---|---:|
| Vertices | 6 |
| Edges | 10 |
| Assignments checked | 64 |
| Exact optimal cut weight | **27** |
| One optimal bitstring | `010110` |
| Complementary optimal bitstring | `101001` |

The two listed bitstrings describe complementary partitions and therefore have the same cut weight. The exact solver provides a reference for evaluating QAOA's expected cut weight and approximation ratio.

## 4. QAOA Method

QAOA alternates between a problem-dependent cost unitary and a mixing unitary. The circuit depth is controlled by \(p\), the number of alternating layers. A classical optimizer updates the variational angles to improve the expected cut objective.

The implementation workflow is:

1. Encode the weighted Max-Cut objective as a cost Hamiltonian.
2. Build the parameterized QAOA circuit for the selected \(p\).
3. Evaluate the objective using circuit samples or expectation estimates.
4. Use a classical optimizer to update the variational parameters.
5. Measure the resulting bitstrings and evaluate their cut weights.
6. Compare the expected cut with the exact classical optimum.

For the initial \(p=1\) run, the optimizer returned:

| Metric | Result |
|---|---:|
| Exact classical optimum | 27 |
| QAOA expected cut weight | 16.9644 |
| Approximation ratio | 0.6283 |
| Optimized \(\gamma\) | 5.47926064 |
| Optimized \(\beta\) | 1.1800038 |
| Optimizer status | Success reported |

The approximation ratio is

\[
r=\frac{\text{QAOA expected cut weight}}{\text{exact optimal cut weight}}
=\frac{16.9644}{27}\approx 0.6283.
\]

**Approximation Ratio = QAOA Expected Cut Weight / Exact Optimal Cut Weight**

= 16.9644 / 27 ≈ 0.6283 (62.83%).

This is an expected-value metric, not a claim that every sampled bitstring achieves that weight. The run also observed an optimal bitstring, but the probability of sampling an optimum depends on the full output distribution and shot count.

## 5. Circuit Depth Study

A separate benchmark compared QAOA depths \(p=1,2,3\). Increasing \(p\) gives the optimizer a more expressive circuit, but it also increases the number of entangling gates and the compiled circuit depth.

### 5.1 Optimized ideal objective

| QAOA depth | Best optimized expected cut | Approximation ratio | CX gates | Reported circuit depth |
|---:|---:|---:|---:|---:|
| \(p=1\) | 20.75742 | 0.7688 | 35 | 52 |
| \(p=2\) | 21.25849 | 0.7874 | 71 | 87 |
| \(p=3\) | 23.43370 | 0.8679 | 120 | 151 |

**Important experiment separation:** these values come from the separate depth benchmark and are not the same run as the initial \(p=1\) result in Section 4. They should not be mixed into one result series. The reported depth values must be interpreted according to the measurement-inclusion convention used by the generating scripts; for a final hardware gate-cost comparison, measurement and reset should be excluded consistently as required by the challenge specification.

### 5.2 Noisy holdout results

| QAOA depth | Mean noisy holdout cut | Optimal-cut probability |
|---:|---:|---:|
| \(p=1\) | 20.0916 | 16.495% |
| \(p=2\) | 19.8222 | 16.793% |
| \(p=3\) | 20.5567 | 26.257% |

The noisy holdout results do not increase monotonically with depth. Although the \(p=3\) experiment has the highest mean noisy cut and optimal-cut probability in this particular benchmark, it also uses substantially more CX gates and greater depth. These results illustrate a practical trade-off rather than proving that a deeper circuit will always perform better.

## 6. Processor Topology and Resource Analysis

### 6.1 Processor B: sparse coupling topology

Processor B is modeled using a nine-qubit sparse coupling graph with edges:

`(0,1), (1,2), (2,3), (2,4), (4,5), (5,6), (4,7), (7,8)`

The logical six-qubit circuit is transpiled to the supported basis gates `rz`, `sx`, `x`, and `cx`. The benchmark uses optimization level 1 and transpiler seed 42.

Reported Processor B resource values:

- Logical qubits: 6
- Compiled CX gates: 35
- Reported circuit depth: approximately 51–52, depending on the output's measurement-inclusion convention

The sparse connectivity may require additional routing operations when the logical circuit's interactions do not directly match physical couplings.

### 6.2 Processor D: custom fully connected simulation

Processor D models a custom six-qubit fully connected topology. Its purpose is to investigate how a topology with direct connectivity between every pair of logical qubits could reduce routing overhead for this problem.

Reported Processor D resource values:

- Logical qubits: 6
- Compiled CX gates: 20
- Reported circuit depth: approximately 29–30, depending on the output's measurement-inclusion convention

Using the reported CX counts, Processor D uses approximately **42.9% fewer CX gates** than Processor B:

\[
\frac{35-20}{35}\times100\%\approx42.9\%.
\]

Using depths 52 and 30 as the compared reported values, the reduction is approximately **42.3%**. Since output conventions may differ, the final submitted resource table should be regenerated from the same metric definitions, with measurements and resets excluded from reported gate cost.

**Scope limitation:** Processor D is a custom topology used in simulation. The results demonstrate a topology/resource comparison under the modeled assumptions; they do not demonstrate execution on a real fully connected quantum device.

### 6.3 Processor A capacity reference

The challenge's Processor A is a five-qubit nearest-neighbor chain, whereas the fixed problem uses six logical qubits. The complete instance therefore does not fit directly on Processor A. The project should report this as a capacity limitation/reference rather than removing a vertex and silently changing the optimization problem.

## 7. Noise Model and Comparison

The processor studies use the challenge-specified style of noise model:

- Single-qubit depolarizing error probability: 0.001
- CX depolarizing error probability: 0.005
- Symmetric readout bit-flip probability: 0.01
- Shots: 4096
- Transpiler optimization level: 1
- Transpiler seed: 42

A separate Processor B versus Processor D noise comparison used ten seeds.

| Metric | Processor B | Processor D |
|---|---:|---:|
| Mean cut weight | 16.7542 | 16.8471 |
| 95% confidence interval | 16.7077–16.8006 | 16.8187–16.8755 |
| Optimal-cut probability | 2.073% | 2.141% |

The observed difference in mean cut weight was **+0.0929** for Processor D relative to Processor B, roughly 0.55% of Processor B's mean. With ten seeds, this difference should be treated as a small observed difference in this experiment—not as proof of a statistically significant or universally better result.

The topology comparison is most clearly supported by the compiled resource counts. Any claim about solution-quality advantage should remain qualified by the finite number of seeds, sampling variation, transpilation behavior, and the assumptions of the noise model.

## 8. Evaluation Metrics

The project uses the following metrics:

- **Cut weight:** total weight of edges crossing the two partitions.
- **Approximation ratio:** QAOA expected cut weight divided by the exact classical optimum.
- **Optimal-cut probability:** fraction of measurement shots that return an optimal solution.
- **CX count:** number of compiled two-qubit controlled-X gates.
- **Circuit depth:** longest sequence of dependent operations after compilation, reported according to the metric convention used by the benchmark.
- **Routing overhead:** additional operations required to satisfy the processor coupling graph, including SWAPs where inserted by transpilation.
- **Noise sensitivity:** change in measured objective and optimal-solution probability under the specified simulated noise assumptions.

For final reporting, gate-cost metrics must be computed consistently after transpilation and must exclude measurement and reset operations, as required by the challenge specification. If SWAP counts are not explicitly extracted by a script, they should be reported as unavailable rather than estimated.

## 9. Reproducibility and Project Artifacts

The repository contains the implementation and experiment artifacts used by the project, including:

- `classical_solver.py` — exhaustive classical reference solver.
- `qaoa_solver.py` — QAOA implementation.
- `GraphCut_Q_walkthrough.ipynb` — notebook walkthrough.
- `qaoa_validation.py` — fixed-parameter validation.
- `qaoa_depth_benchmark.py` — depth comparison.
- `qaoa_strong_benchmark.py` — repeated/stronger benchmark workflow.
- `processor_benchmark.py` — Processor B resource benchmark.
- `processor_d_benchmark.py` — custom Processor D benchmark.
- `processor_noise_comparison.py` — Processor B/D noise comparison.
- `noise_benchmark.py` and `noise_sensitivity.py` — noise experiments.
- CSV, JSON, and NPZ files — experiment logs, metrics, and saved parameters.
- `figures/` and `classical_graph.png` — visual artifacts.
- `requirements.txt` — Python dependencies.
- `README.md` — project overview and setup instructions.

To reproduce the experiments, use the setup and run commands documented in the repository README and each script's own interface. Run from the repository root in the intended Python environment. Benchmark outputs may vary if dependency versions, random seeds, transpilation settings, shots, or optimizer settings change.

## 10. Limitations

1. **Small instance:** six vertices make exhaustive search practical and do not establish performance on large-scale graphs.
2. **Simulation-based hardware comparison:** the Processor B and Processor D results are modeled simulations, not a claim of physical-device execution.
3. **Sampling variation:** finite shots and a finite number of seeds introduce uncertainty.
4. **Optimizer dependence:** QAOA results can depend on initialization, optimizer behavior, and parameter landscape.
5. **Metric consistency:** circuit depth and routing statistics must use identical counting conventions across processor models. Measurement and reset should be excluded from the reported gate-cost comparison.
6. **Topology assumptions:** the fully connected Processor D model isolates a connectivity hypothesis; real hardware would also have calibration, crosstalk, coherence, and control constraints not fully captured by a simplified noise model.

## 11. Conclusion

GraphCut-Q combines an exact classical baseline with QAOA optimization, depth benchmarking, topology-aware compilation, and simulated noise analysis for a fixed weighted Max-Cut instance. The exact optimum is 27. In the initial \(p=1\) run, QAOA achieved an expected cut weight of 16.9644 and an approximation ratio of 0.6283. A separate depth study showed improved optimized objective values at higher \(p\), accompanied by a larger CX count and greater circuit depth.

The Processor B/D comparison suggests that a fully connected custom topology can reduce compiled two-qubit gate count for this circuit under the modeled conditions. However, Processor D is simulated, and the observed noise-performance difference is small and based on ten seeds. The most defensible conclusion is that **topology and circuit depth materially affect resource cost, while solution quality must be interpreted alongside sampling uncertainty and the assumptions of the noise model**.

## 12. Final Verification Checklist

Before submitting the report, verify these items against the final repository state:

- [ ] All reported values match the committed CSV/JSON/NPZ artifacts.
- [ ] The same six-vertex graph is used in the required processor comparisons.
- [ ] Circuit depth and CX count are regenerated with measurement/reset excluded from gate-cost reporting.
- [ ] SWAP/routing overhead is explicitly reported from actual transpiler data where available.
- [ ] Processor D is clearly labeled as a simulated custom topology.
- [ ] The notebook runs end-to-end in the documented environment.
- [ ] Setup and execution commands in `README.md` work from a clean checkout.
- [ ] The report, notebook, scripts, configuration files, and result artifacts are committed to GitHub.
- [ ] Team registration and submission through the official hackathon portal are complete.

---

**Reproducibility note:** This report summarizes the experiment values currently documented for GraphCut-Q. Before final submission, cross-check every table against the latest committed result files—especially circuit depth conventions and the exact scripts that produced each benchmark.
