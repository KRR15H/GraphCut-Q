"""
GraphCut-Q result plots.
Run from the project root:
    python plot_results.py
Requires: pandas, matplotlib
Reads existing CSV results only; does not rerun QAOA.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT / name}")

# Strong benchmark: frozen parameters, holdout seeds
strong = pd.read_csv(ROOT / "qaoa_strong_summary.csv").sort_values("p")
x = strong["p"].astype(str)

fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.errorbar(x, strong["ideal_mean"], yerr=strong["ideal_sd"], marker="o",
            capsize=4, linewidth=2, label="Ideal simulation")
ax.errorbar(x, strong["noisy_mean"], yerr=strong["noisy_sd"], marker="s",
            capsize=4, linewidth=2, label="Noisy simulation")
ax.axhline(27, linestyle="--", linewidth=1.5, label="Exact optimum = 27")
ax.set(title="QAOA cut quality vs depth", xlabel="QAOA depth p",
       ylabel="Mean cut weight")
ax.grid(True, alpha=.25)
ax.legend()
save(fig, "strong_mean_cut.png")

fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.plot(x, strong["noise_gap"], marker="o", linewidth=2)
ax.set(title="Noise penalty grows with QAOA depth", xlabel="QAOA depth p",
       ylabel="Ideal mean − noisy mean")
ax.grid(True, alpha=.25)
save(fig, "noise_penalty.png")

fig, ax1 = plt.subplots(figsize=(7.4, 4.6))
ax1.plot(x, strong["cx_count"], marker="o", linewidth=2, label="CX gates")
ax1.set_xlabel("QAOA depth p")
ax1.set_ylabel("CX gate count")
ax1.grid(True, alpha=.25)
ax2 = ax1.twinx()
ax2.plot(x, strong["circuit_depth"], marker="s", linewidth=2, label="Circuit depth")
ax2.set_ylabel("Circuit depth")
ax1.set_title("Circuit resource cost vs QAOA depth")
lines = ax1.get_lines() + ax2.get_lines()
ax1.legend(lines, [line.get_label() for line in lines], loc="upper left")
save(fig, "resource_cost.png")

fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.errorbar(x, 100 * strong["noisy_optimal_probability"],
            yerr=100 * (strong["noisy_optimal_probability_sd"]),
            marker="o", capsize=4, linewidth=2)
ax.set(title="Observed optimal bitstring probability (noisy simulation)",
       xlabel="QAOA depth p", ylabel="Optimal bitstring probability (%)")
ax.grid(True, alpha=.25)
save(fig, "optimal_probability.png")

# Noise-sensitivity sweep (if present)
noise_path = ROOT / "noise_sensitivity_results.csv"
if noise_path.exists():
    noise = pd.read_csv(noise_path)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.errorbar(noise["noise_level"], noise["mean_average_cut"],
                yerr=noise["std_average_cut"], marker="o", capsize=4, linewidth=2)
    ax.set(title="Sensitivity to simulated noise", xlabel="Noise setting",
           ylabel="Mean cut weight")
    ax.grid(True, alpha=.25)
    save(fig, "noise_sensitivity.png")

print("\nDone. Figures are in the figures/ directory.")
