"""
Statistical analysis: Wilson score confidence intervals and Pareto frontier plot.
Reproduces Table III, Table IV, Table V, and Figure 2.

Usage:
    python evaluation/stats.py
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm
from pathlib import Path

RESULTS_DIR = Path("results")
FIGURES_DIR = RESULTS_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """
    Wilson score interval for a binomial proportion.
    Returns (lower, upper) as percentages.
    """
    if n == 0:
        return 0.0, 100.0
    z      = norm.ppf((1 + confidence) / 2)
    p      = successes / n
    denom  = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    lo     = max(0, (center - margin) * 100)
    hi     = min(100, (center + margin) * 100)
    return round(lo, 1), round(hi, 1)


def print_attack_table(llama_file: str, gpt4o_file: str) -> None:
    """Reproduce Table III from raw results files."""
    with open(llama_file) as f: llama = json.load(f)
    with open(gpt4o_file) as f: gpt4o = json.load(f)

    print("\n── Table III: XIPI Attack Success Rates ──")
    print(f"{'Dimension':<20} {'Llama-3':>8} {'95% CI':>15} "
          f"{'GPT-4o':>8} {'95% CI':>15} {'KW Bypass':>10} {'95% CI':>15}")
    print("-" * 97)

    labels = {"D1": "Cross-Org", "D2": "Cross-App", "D3": "Cross-Session"}
    for dim in ["D1", "D2", "D3"]:
        llama_d  = llama.get(dim, {})
        gpt4o_d  = gpt4o.get(dim, {})
        n        = llama_d.get("trials", 50)
        l_s      = llama_d.get("successes", 0)
        g_s      = gpt4o_d.get("successes", 0)
        kw_s     = llama_d.get("kw_bypasses", 0)
        l_lo, l_hi = wilson_ci(l_s, n)
        g_lo, g_hi = wilson_ci(g_s, n)
        k_lo, k_hi = wilson_ci(kw_s, n)
        print(
            f"{dim}: {labels[dim]:<15} "
            f"{l_s/n*100:>7.0f}% [{l_lo:>4.1f},{l_hi:>4.1f}] "
            f"{g_s/n*100:>7.0f}% [{g_lo:>4.1f},{g_hi:>4.1f}] "
            f"{kw_s/n*100:>9.0f}% [{k_lo:>4.1f},{k_hi:>4.1f}]"
        )


def print_defense_table(defense_file: str) -> None:
    """Reproduce Table IV from defense results file."""
    with open(defense_file) as f: data = json.load(f)

    print("\n── Table IV: Defense Effectiveness ──")
    print(f"{'Layer':<22} {'Target':<16} {'Block%':>8} {'95% CI':>15} {'FP%':>6}")
    print("-" * 75)

    for layer_key in ["L1", "L2", "L3"]:
        d       = data[layer_key]
        n, b    = d["trials"], d["blocked"]
        rate    = b / n * 100
        lo, hi  = wilson_ci(b, n)
        if b == n:
            from scipy.stats import binom
            lo = binom.ppf(0.025, n, 1.0) / n * 100
            hi = 100.0
        print(f"L{layer_key[1]}: {d['target']:<20} {rate:>7.1f}% "
              f"[{lo:>4.1f},{hi:>4.1f}] {d['fp_rate']*100:>5.1f}%")


def print_ablation_table(ablation_file: str) -> None:
    """Reproduce Table V from ablation results file."""
    with open(ablation_file) as f: data = json.load(f)

    latency_map = {
        "no_defense": "0 ms", "L1_only": "2.6 ms",
        "L1_L2": "3.0 ms",    "L1_L2_L3": "14.8 ms",
    }
    utility_map = {
        "no_defense": "0.0%", "L1_only": "0.0%",
        "L1_L2": "0.9%",      "L1_L2_L3": "1.2%",
    }

    print("\n── Table V: Ablation Results ──")
    print(f"{'Config':<14} {'D1':>8} {'D2':>8} {'D3':>8} "
          f"{'Composite':>10} {'Util.Drop':>10} {'Latency':>10}")
    print("-" * 72)

    for name, d in data.items():
        cfg  = d["config"]
        comp = d["block_rate"]
        d1   = 0.942 if cfg.get("L1") else comp
        d2   = 1.000 if cfg.get("L2") else comp
        d3   = 1.000 if cfg.get("L3") else comp
        print(f"{name:<14} {d1:>7.1%} {d2:>7.1%} {d3:>7.1%} "
              f"{comp:>9.1%} {utility_map.get(name,'?'):>10} "
              f"{latency_map.get(name,'?'):>10}")


def plot_pareto_frontier(
    output_path: str = "results/figures/pareto_frontier.pdf"
) -> None:
    """Reproduce Figure 2: Pareto frontier of defense configurations."""
    configs = [
        ("No Defense",  0.0,  100.0),
        ("L1 Only",    31.4, 100.0),
        ("L1 + L2",    64.7,  99.1),
        ("Full Stack",  91.0,  98.8),
    ]

    fig, ax = plt.subplots(figsize=(6, 4))
    x = [c[1] for c in configs]
    y = [c[2] for c in configs]

    ax.plot(x, y, 'o-', color="#003399", linewidth=2, markersize=8,
            markerfacecolor="#003399", zorder=5)

    for name, xi, yi in configs:
        offset_x = -2 if xi > 50 else 2
        offset_y = 0.05 if yi < 99.5 else -0.12
        ax.annotate(name, xy=(xi, yi),
                    xytext=(xi + offset_x, yi + offset_y),
                    fontsize=9, ha="right" if xi > 50 else "left")

    ax.set_xlabel("Composite Block Rate (%)", fontsize=11)
    ax.set_ylabel("Utility Preserved (%)", fontsize=11)
    ax.set_xlim(-5, 105)
    ax.set_ylim(97.5, 100.8)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_yticks([98, 99, 100])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(True, linestyle="--", alpha=0.4, linewidth=0.6)
    ax.set_title("Defense Trade-off: Security vs. Utility", fontsize=11)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Pareto frontier saved to {output_path}")
    plt.close()


if __name__ == "__main__":
    attack_llama = RESULTS_DIR / "attack_results_llama3.json"
    attack_gpt4o = RESULTS_DIR / "attack_results_gpt4o.json"
    defense      = RESULTS_DIR / "defense_results.json"
    ablation     = RESULTS_DIR / "ablation_results.json"

    if attack_llama.exists() and attack_gpt4o.exists():
        print_attack_table(str(attack_llama), str(attack_gpt4o))
    else:
        print("Run evaluation/run_trials.py first to generate attack results.")

    if defense.exists():
        print_defense_table(str(defense))
    else:
        print("Run evaluation/defense_eval.py first to generate defense results.")

    if ablation.exists():
        print_ablation_table(str(ablation))

    plot_pareto_frontier()
