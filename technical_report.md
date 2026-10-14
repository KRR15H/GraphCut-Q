# GraphCut-Q: Hardware-Aware QAOA for Weighted Max-Cut

## Abstract
GraphCut-Q studies the Quantum Approximate Optimization Algorithm (QAOA) for a six-vertex weighted Max-Cut instance. It compares ideal and noisy circuit simulations across QAOA depths p = 1, 2, and 3, and records circuit-resource costs. The exact classical optimum for the development graph is 27. The strongest reported experiment freezes parameters selected during optimization and evaluates them on 30 holdout seeds with 4,096 shots per seed. Results show that deeper circuits can improve sampled cut quality, while increasing CX count, circuit depth, and the observed noise penalty.

## Problem definition
For a weighted graph G = (V, E), assign each vertex a binary label x_i. The cut weight is the sum of weights for edges whose endpoints receive different labels:

\[
C(x) = \sum_{(i,j)\in E} w_{ij}[x_i \ne x_j].
\]

The objective is to find a bitstring maximizing C(x). The project uses a six-vertex graph and reports an exact classical optimum of 27. Before final submission, confirm that this graph is the organizer-approved instance; the value 27 refers to the graph currently implemented in the project.

## Method
1. Compute the exact classical optimum by enumerating all 2^6 bitstrings.
2. Construct QAOA circuits for p = 1, 2, and 3.
3. Optimize parameters, then freeze the selected parameters for the strong benchmark.
4. Evaluate ideal and noisy simulations over 30 holdout seeds, with 4,096 shots per seed.
5. Record mean cut weight, variability, confidence intervals, optimal-bitstring probability, CX count, and circuit depth.
6. Compile a Processor B circuit against the provided coupling graph and record routing/resource metrics.

## Main results: frozen-parameter holdout benchmark

| p | Fixed expected cut | Approx. ratio | Ideal mean ± SD | Noisy mean ± SD | Noise gap | CX gates | Depth |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.757 | 0.769 | 20.734 ± 0.062 | 20.092 ± 0.058 | 0.642 | 35 | 52 |
| 2 | 21.258 | 0.787 | 21.228 ± 0.064 | 19.822 ± 0.074 | 1.406 | 71 | 87 |
| 3 | 23.434 | 0.868 | 23.421 ± 0.056 | 20.557 ± 0.086 | 2.864 | 120 | 151 |

The approximation ratio in this table is the fixed expected cut divided by the exact optimum 27. Confidence intervals are available in `qaoa_strong_summary.csv`; report them in a presentation if space allows.

## Interpretation
- In this experiment, p = 3 had the highest ideal and noisy mean cut weight.
- Increasing depth from p = 1 to p = 3 increased the CX count from 35 to 120 and depth from 52 to 151.
- The observed ideal-to-noisy mean gap increased from about 0.642 at p = 1 to about 2.864 at p = 3.
- The best depth depends on the objective: p = 3 gives the best observed noisy mean here, but p = 1 has lower circuit cost and a smaller noise penalty.
- These are simulator results. They do not establish quantum advantage and should not be described as hardware execution results.

## Processor mapping
The recorded Processor B benchmark reports 9 physical qubits available, 6 logical qubits required, 8 coupling edges, 35 CX gates, depth 51, and zero SWAP gates for that compiled circuit. The p = 1 resource figures in the strong benchmark show depth 52; this one-layer difference likely reflects distinct circuit/compilation paths and should be explained or normalized before claiming a single canonical depth.

Processor A requires special treatment because one supplied challenge document describes only five qubits, fewer than the six logical qubits needed. The challenge documents also appear to disagree on Processor A's topology. Verify the authoritative topology with the organizers and document the chosen interpretation. Processor D's expected architecture/result must also be checked against the official kit before final submission.

## Limitations and reproducibility
- Results are specific to the graph, parameter selection, transpilation, noise model, and shot count used in this implementation.
- Do not combine `qaoa_depth_results.csv`, `qaoa_tradeoff_results.csv`, `qaoa_validation_results.csv`, and `qaoa_strong_summary.csv` into one series: they represent separate experiments and contain different parameter choices.
- Verify that the noise model matches the challenge specification exactly and that the same graph is used for all processor comparisons.
- Record Qiskit and Python versions, random seeds, optimization settings, and exact run commands in the README or appendix.
- Confirm the graph instance and Processor A/Processor D definitions against the official challenge material.

## Conclusion
GraphCut-Q demonstrates a measurable depth–quality–noise trade-off for QAOA on a weighted Max-Cut problem. In the frozen-parameter holdout experiment, p = 3 achieved the highest noisy mean cut weight but required substantially more entangling gates and circuit depth. The result supports hardware-aware depth selection—not a claim of quantum advantage.
