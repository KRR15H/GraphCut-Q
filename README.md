# GraphCut-Q

**A hardware-aware QAOA study for weighted Max-Cut**

*Qiskit Fall Fest 2026 · Quantum Optimization · QAOA / Max-Cut*

------------------------------------------------------------------------

## The idea

Quantum optimization is not just about finding a good answer. The
circuit must also survive the realities of hardware: limited
connectivity, extra two-qubit gates, finite shots, and noise.

**GraphCut-Q** studies that trade-off using the Quantum Approximate
Optimization Algorithm (QAOA) on a six-vertex weighted Max-Cut instance.
It combines an exact classical reference, variational parameter
optimization, hardware-aware transpilation, and repeated
noisy-simulation experiments.

The central question is:

> **When a deeper QAOA circuit improves the ideal solution, does that
> improvement survive hardware connectivity and noise?**

## What this project does

-   **Builds a classical reference:** exhaustively evaluates all (2\^6
    = 64) assignments to find the exact optimum for the development
    graph.
-   **Encodes Max-Cut for QAOA:** represents weighted edges with
    cost-Hamiltonian interactions and applies alternating cost and mixer
    layers.
-   **Optimizes variational parameters:** uses a classical COBYLA
    optimizer with multiple random restarts.
-   **Compiles for a target architecture:** transpiles to the native
    basis `rz`, `sx`, `x`, and `cx`, using a fixed transpiler seed.
-   **Models device noise:** includes depolarizing gate noise and
    symmetric readout bit-flips.
-   **Runs holdout validation:** freezes optimized parameters before
    evaluating 30 separate simulator seeds, with 4,096 shots per seed.
-   **Measures the trade-off:** records expected cut weight,
    approximation ratio, optimal-bitstring frequency, circuit depth, and
    CX count.

## Headline result

For the current **development graph** and the configured Processor B
noise model, the strongest experiment found that depth (p=3) achieved
the highest noisy mean cut weight among the three tested depths.

  -----------------------------------------------------------------------------------
   QAOA depth    Ideal mean    Noisy mean    CX gates    Compiled               Noisy
                        cut           cut                   depth   optimal-bitstring
                                                                            frequency
  ----------- ------------- ------------- ----------- ----------- -------------------
        p = 1       20.7339       20.0916          35          52             16.495%

        p = 2       21.2279       19.8222          71          87             16.793%

    **p = 3**   **23.4207**   **20.5567**         120         151         **26.257%**
  -----------------------------------------------------------------------------------

**How to read this:** p=3 produced the best observed noisy mean and
optimal-bitstring frequency in this experiment, but it also required
substantially more CX gates and circuit depth. This is evidence of a
quality--resource trade-off on this graph and noise model---not proof of
quantum advantage or a hardware result.

The table reports the 30-seed holdout experiment. Values are
experiment-specific; rerun the scripts to reproduce them in your
environment.

## Architecture matters

The project models Processor B as a sparse nine-qubit coupling graph and
compiles the six-qubit logical circuit to its native gate basis. In an
earlier compilation benchmark, the Processor B circuit required **35 CX
gates at depth 51--52**, compared with **20 CX gates at depth 29** for
the unconstrained logical baseline. Routing overhead can appear as
additional CX gates even when the final transpiled circuit reports zero
explicit SWAP instructions.

Processor A has only five qubits, so it **cannot directly host this
six-qubit logical instance** without changing the encoding or reducing
the problem. Treat Processor A as a capacity/routing reference unless an
approved qubit-reduction method is implemented.

## Experimental setup

The current benchmark configuration uses:

-   **Problem:** six vertices, integer-weighted edges
-   **Classical reference:** exhaustive search over 64 bitstrings
-   **QAOA depths:** p = 1, 2, 3 for the depth study
-   **Optimizer:** COBYLA, with multiple random initializations
-   **Native basis:** `rz`, `sx`, `x`, `cx`
-   **Transpilation:** optimization level 1, transpiler seed 42
-   **Noise:** single-qubit depolarizing probability 0.001; CX
    depolarizing probability 0.005; symmetric readout bit-flip
    probability 0.01
-   **Sampling:** 4,096 shots per simulator run
-   **Holdout validation:** 30 seeds per depth in the strongest
    benchmark

These are simulator experiments using a configured noise model, not
measurements from a physical quantum processor.

## Repository map

The project has been developed as a collection of focused scripts and
CSV outputs:

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `classical_solver.py`               Classical Max-Cut reference and
                                      exact optimum

  `qaoa_solver.py`                    QAOA circuit, cut-weight
                                      evaluation, and parameter
                                      optimization

  `measurement_simulator.py`          Measurement / bitstring sampling
                                      utilities

  `processor_benchmark.py`            Architecture-aware transpilation
                                      comparison

  `noise_benchmark.py`                Single-run ideal-versus-noisy
                                      comparison

  `repeated_benchmark.py`             Repeated-seed noise benchmark

  `noise_sensitivity.py`              Noise-level sensitivity experiment

  `qaoa_depth_benchmark.py`           QAOA depth comparison

  `qaoa_tradeoff.py`                  Exploratory quality-versus-CX
                                      scoring

  `qaoa_validation.py`                Fixed-parameter validation across
                                      seeds

  `qaoa_strong_benchmark.py`          Multi-restart optimization and
                                      holdout evaluation

  `processor_benchmark_results.csv`   Architecture benchmark results

  `repeated_benchmark_results.csv`    Repeated-seed results

  `noise_sensitivity_results.csv`     Noise-sweep results

  `qaoa_depth_results.csv`            Depth experiment results

  `qaoa_tradeoff_results.csv`         Exploratory trade-off results

  `qaoa_validation_results.csv`       Fixed-parameter validation results

  `qaoa_strong_seed_results.csv`      Seed-level strong-benchmark results

  `qaoa_strong_summary.csv`           Strong-benchmark summary

  `qaoa_strong_metadata.json`         Strong-benchmark configuration /
                                      metadata

  `qaoa_strong_parameters.npz`        Frozen parameters selected by the
                                      strong benchmark
  -----------------------------------------------------------------------

File names reflect the current development layout; if your local folder
differs, update this map before submitting.

## Run it locally

Use Python 3.10+ and a virtual environment. Install the dependencies
used by your scripts (at minimum Qiskit, Qiskit Aer, NumPy, and SciPy;
add any plotting or visualization libraries your local code imports).

### Windows PowerShell

``` powershell
# From the GraphCut-Q project folder
py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install qiskit qiskit-aer numpy scipy
```

Run an individual experiment:

``` powershell
python classical_solver.py
python processor_benchmark.py
python qaoa_strong_benchmark.py
```

Run the scripts in the order appropriate to your workflow. Some
benchmark scripts may take several minutes because they optimize
parameters and execute repeated shot-based simulations. Confirm each
script's imports and CLI behavior in your local environment before using
these commands in a final demo.

## Metrics explained

-   **Cut weight:** sum of the weights of edges whose endpoints receive
    different bit values.
-   **Exact optimum:** the maximum cut weight found by exhaustive
    classical enumeration.
-   **Approximation ratio:** expected or observed cut weight divided by
    the exact optimum. State which cut-weight statistic is used whenever
    reporting this ratio.
-   **Optimal-bitstring frequency:** fraction of measured shots that
    produce an optimal assignment. For Max-Cut, complementary bitstrings
    represent the same partition.
-   **CX count and circuit depth:** compiled resource indicators used to
    compare architecture costs.
-   **Noisy--ideal gap:** difference between ideal and noisy mean cut
    weight under the same frozen parameters and evaluation protocol.

## Important limitations

1.  **Official instance check:** the graph currently used in the scripts
    is a development instance. Before submission, replace or confirm it
    against the organizer-approved instance and use the same graph for
    every required architecture comparison.
2.  **Processor A feasibility:** a six-qubit logical instance does not
    fit directly on a five-qubit Processor A. Document this constraint
    and implement an approved reduction or clearly scope A as a capacity
    reference.
3.  The Processor B and custom Processor D benchmark comparisons have been implemented and documented. Results are based on simulated execution under the configured noise model; Processor D represents a proposed architecture, not physical quantum hardware.
4.  **Conflicting architecture documents:** the supplied challenge
    materials appear to describe Processor A differently in different
    versions. Confirm the authoritative topology with the organizers; do
    not mix topologies in the final report.
5.  **Reproducibility:** preserve package versions, seeds, parameters,
    and the exact commands used. Rerun the final results from a clean
    environment before submission.
6.  **No quantum-advantage claim:** this is a small, classically
    tractable benchmark intended to study QAOA behavior and
    hardware-resource trade-offs.

---------------------------------------------------------------------

## Why GraphCut-Q?

GraphCut-Q is designed to tell a complete experimental story:
**establish the truth classically, optimize variationally, compile
against real architectural constraints, then test the result under
noise.** The goal is not to make the circuit look impressive on
paper---it is to quantify what is gained, what it costs, and where the
hardware changes the answer.

------------------------------------------------------------------------

## Contributors

- **Krrish Raj Kannojia** — Project implementation, QAOA and classical solver, benchmarking, and integration.
- **Siddhi Kapoor** — Research and Study, Helping hand in Implimentation and integration and Documentation

Built collaboratively for the Qiskit Fall Fest 2026 Quantum Optimization challenge.

*Status: research prototype / benchmark suite. Verify the official
challenge instance and complete the submission checklist before treating
this README as final.*
