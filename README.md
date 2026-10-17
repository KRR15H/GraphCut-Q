# GraphCut-Q
### Hardware-aware QAOA for Weighted Max-Cut

GraphCut-Q studies how the **Quantum Approximate Optimization Algorithm (QAOA)** can solve a weighted Max-Cut problem and how circuit connectivity, compilation, and noise influence the result.

The project combines an exact classical baseline with a parameterized quantum circuit, then evaluates that circuit under different simulated processor architectures. The aim is to find high-quality cuts while measuring the practical cost of mapping the same optimization problem to different hardware layouts.

> **Scope:** Processor B and Processor D results are simulation-based. Processor D is a proposed custom topology used for architecture comparison, not a physical quantum processor.

## At a glance

| Item | Value |
|---|---|
| Problem | Weighted Max-Cut |
| Graph | 6 vertices, 10 weighted edges |
| Edge weights | Integers from 1 to 5 |
| Exact classical optimum | **27** |
| Quantum method | QAOA |
| Main tools | Python, Qiskit |
| Evaluation | Classical baseline, QAOA, depth study, architecture and noise benchmarks |

## Why this project?

A circuit can be mathematically correct and still be expensive to execute on a particular device. Limited connectivity can introduce routing operations, while gate and readout noise can change the measured output distribution.

GraphCut-Q investigates this gap between an optimization model and its hardware-aware implementation:

- Formulate weighted Max-Cut as a binary objective and cost Hamiltonian.
- Build a QAOA circuit and optimize its parameters with a classical optimizer.
- Compare QAOA results with an exact classical solution.
- Transpile the same logical problem for different connectivity assumptions.
- Measure circuit depth and two-qubit gate counts.
- Compare ideal and noisy simulation results across repeated runs.
- Study the quality-versus-cost trade-off as QAOA depth increases.

## Problem formulation

Given a weighted undirected graph \(G=(V,E)\), assign each vertex to one of two sets. An edge contributes its weight when its endpoints are assigned to different sets.

Let \(x_i\in\{0,1\}\) represent the set assignment of vertex \(i\). The objective is to maximize

\[
C(x)=\sum_{(i,j)\in E} w_{ij}\,[x_i+x_j-2x_ix_j].
\]

For this instance, the graph has six vertices and ten weighted edges. The classical solver checks all \(2^6=64\) assignments and finds a maximum cut weight of **27**. One optimal bitstring is `010110`; its complement `101001` represents the same cut with the two partitions swapped.

### QUBO and cost Hamiltonian

The equivalent QUBO can be expressed as minimization of the negative cut weight:

\[
Q(x)=-\sum_{(i,j)\in E}w_{ij}(x_i+x_j-2x_ix_j).
\]

Using \(x_i=(1-Z_i)/2\), the Max-Cut cost Hamiltonian is

\[
H_C=\sum_{(i,j)\in E}\frac{w_{ij}}{2}(I-Z_iZ_j).
\]

The cost Hamiltonian defines the QAOA cost layer. Cost and mixer layers are repeated according to depth \(p\), while a classical optimizer searches for useful angle parameters.

## Method

1. **Exact baseline:** enumerate every bitstring for the six-vertex graph and record the best cut.
2. **QAOA construction:** encode the cost Hamiltonian and build a parameterized circuit.
3. **Parameter optimization:** use a classical optimizer to search over the QAOA angles.
4. **Sampling and validation:** evaluate sampled bitstrings, expected cut value, and optimal-cut probability.
5. **Compilation and architecture study:** transpile the logical circuit for the specified coupling maps and compare resource counts.
6. **Noise experiments:** compare ideal and noisy simulations, including repeated-seed and noise-sensitivity studies.

## Results

### Core QAOA run

| Metric | Result |
|---|---:|
| Exact classical optimum | 27 |
| QAOA expected cut, \(p=1\) | 16.9644 |
| Approximation ratio | 0.6283 |
| Optimizer | COBYLA |
| Optimizer status | Returned successfully |

The approximation ratio is

\[
r=\frac{\mathbb{E}[C_{\mathrm{QAOA}}]}{C_{\mathrm{optimal}}}.
\]

For this run, \(r=16.9644/27\approx0.6283\). This is an expected objective value, not a claim that every sample reaches that value. An optimal bitstring was observed during sampling.

### QAOA depth study

A separate benchmark investigated the trade-off between solution quality and circuit cost.

| Depth | Ideal expected cut | Noisy holdout mean cut | Optimal-cut probability | CX gates | Recorded circuit depth* |
|---:|---:|---:|---:|---:|---:|
| \(p=1\) | 20.7574 | 20.0916 | 16.495% | 35 | 52 |
| \(p=2\) | 21.2585 | 19.8222 | 16.793% | 71 | 87 |
| \(p=3\) | 23.4337 | 20.5567 | 26.257% | 120 | 151 |

These values come from the depth-comparison experiment and are **not** the same run as the core \(p=1\) result above. Interpret them within that experiment's evaluation setup.

\*Recorded depth values may include measurement operations. For gate-cost comparisons, report depth with measurements excluded when the benchmark specification requires it.

The depth study illustrates a practical trade-off: deeper circuits can improve ideal objective values, but require more two-qubit gates and greater depth, increasing exposure to noise.

### Processor architecture comparison

The same six-qubit logical problem was compared on two simulated connectivity models.

| Metric | Processor B | Processor D |
|---|---:|---:|
| Logical qubits | 6 | 6 |
| Connectivity | Sparse, 9-qubit heavy-hex-inspired graph | Fully connected, 6-qubit custom topology |
| Compiled CX gates | 35 | 20 |
| Recorded compiled depth | 52 | 30 |
| Mean noisy cut (10-seed comparison) | 16.7542 | 16.8471 |
| 95% confidence interval for mean cut | 16.7077–16.8006 | 16.8187–16.8755 |
| Optimal-cut probability | 2.073% | 2.141% |

For this comparison, the Processor D model uses **15 fewer CX gates**, a reduction of approximately **42.9%** relative to Processor B. The recorded depth is also lower. The ten-seed noisy comparison shows a small difference in mean cut value; it is not sufficient by itself to establish statistical significance.

**Interpretation:** The custom topology reduces routing pressure for this instance in simulation. This is a topology-dependent resource comparison, not a claim about the performance of a real device. Depth and gate counts should be compared using the same counting convention, ideally excluding measurements from gate-cost metrics.

### Noise sensitivity

The noise experiments compare ideal execution with simulated noise at several strengths and repeat runs across seeds. The analysis tracks mean cut value, optimal-cut probability, changes in the measured objective as noise strength increases, and variation across independent seeds.

Noise results are empirical estimates from finite-shot simulations. Interpret them alongside the shot count, seed count, and confidence intervals rather than as exact hardware predictions.

## Hardware model and assumptions

The processor experiments use explicit coupling maps rather than assuming every pair of qubits can interact directly.

- **Processor B:** nine physical-qubit positions with sparse connectivity; the logical circuit is transpiled to the specified topology.
- **Processor D:** a proposed six-qubit fully connected topology used to study how connectivity changes compilation cost.
- **Processor A:** a five-qubit nearest-neighbour chain. It cannot hold the full six-logical-qubit instance simultaneously, so it is treated as a capacity/routing reference rather than dropping a problem variable.
- **Noise model:** the configured simulation experiments use single-qubit depolarizing error, two-qubit depolarizing error, and readout bit-flip error. Check each benchmark script for the exact configuration used in that experiment.

Processor D is a **simulated architecture proposal**, not an IBM device or a claim of physical execution. Architecture comparisons are meaningful only when graph instance, logical circuit, transpilation settings, shot count, noise assumptions, and metric definitions are consistent.

## Repository structure

```text
GraphCut-Q/
├── classical_solver.py              # Exact classical Max-Cut baseline
├── qaoa_solver.py                   # QAOA implementation and optimization
├── GraphCutQ_walkthrough.ipynb      # End-to-end walkthrough
├── qaoa_validation.py               # Fixed-parameter validation
├── qaoa_depth_benchmark.py           # QAOA depth comparison
├── qaoa_strong_benchmark.py          # Repeated/stronger benchmark runs
├── processor_benchmark.py           # Processor B compilation/resource study
├── processor_d_benchmark.py          # Custom Processor D study
├── processor_noise_comparison.py     # B/D noisy comparison
├── noise_benchmark.py                # Ideal/noisy execution comparison
├── noise_sensitivity.py              # Noise-strength sensitivity
├── qaoa_tradeoff.py                  # Quality/resource trade-off analysis
├── requirements.txt                  # Python dependencies
├── technical_report.md               # Extended technical report
└── figures/                          # Generated plots, if present
```

The repository also includes CSV/JSON benchmark outputs, saved parameter files, and other experiment artifacts. The exact set of generated files may evolve as experiments are rerun.

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/KRR15H/GraphCut-Q.git
cd GraphCut-Q
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the baseline and QAOA solver

```bash
python classical_solver.py
python qaoa_solver.py
```

For notebook-based exploration, install Jupyter and open `GraphCutQ_walkthrough.ipynb`:

```bash
python -m pip install notebook
jupyter notebook
```

### 5. Run additional experiments

Run scripts individually when you want to regenerate their associated results:

```bash
python qaoa_validation.py
python qaoa_depth_benchmark.py
python processor_benchmark.py
python processor_d_benchmark.py
python processor_noise_comparison.py
python noise_benchmark.py
python noise_sensitivity.py
```

Some experiments may take longer because they run multiple seeds, shots, or parameter settings. A run may regenerate or overwrite output files; preserve results you need before rerunning it.

## Reproducibility

- Use the same graph instance for all architecture comparisons.
- Record QAOA depth, optimizer settings, initial parameters, random seeds, and shots.
- Keep ideal and noisy results separate.
- State whether circuit depth includes measurement operations.
- Report transpiled two-qubit gate counts and routing overhead using consistent definitions.
- Treat finite-shot probabilities and means as estimates.
- Use benchmark scripts and saved CSV/JSON artifacts to trace results to their experiment.

Results may vary if seeds, software versions, optimizer settings, or compilation options change.

## Limitations

- The graph is small enough for exact classical enumeration. This supports validation but does not demonstrate a quantum speedup.
- QAOA performance depends on depth, parameter optimization, and sampling variance.
- Noisy simulations model selected error channels; they are not a substitute for calibration data or physical-device execution.
- Processor D is a hypothetical connectivity design evaluated in simulation.
- Results depend on the graph, circuit, transpiler configuration, and noise assumptions.

## Team

- **Krrish Raj Kannojia** — project implementation, QAOA and classical-solver integration, benchmarking, and experimental analysis.
- **Siddhi Kapoor** — DOCUMENTATION , Research and Study, Helping hand in implementation and project integration

## Acknowledgements

Built for the Qiskit Fall Fest 2026 quantum optimization track. The project uses Python and Qiskit to study QAOA, weighted Max-Cut, circuit compilation, and noise-aware evaluation.

---

**Repository:** https://github.com/KRR15H/GraphCut-Q
