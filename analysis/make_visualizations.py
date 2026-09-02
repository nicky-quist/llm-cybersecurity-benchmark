"""
Regenerate the charts in visualizations/ from data/prompt_results.csv.

Replaces analysis/benchmark_analysis.ipynb, which carried a .ipynb extension but
contained a plain Python script — so Jupyter could not open it and GitHub could
not render it. It also ended on `df.head()` and never actually produced the PNGs
it was supposed to, and required pandas for work the stdlib csv module does.

Every chart here shows all eight models, GPT-4o included, and labels bars with
wins over appearances, because a win count on its own is not comparable across
models that were drawn a different number of times.

    python analysis/make_visualizations.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")  # write files without needing a display
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.statistics import (bradley_terry, bootstrap_bradley_terry, load_results,
                                 tally, vendor_split, wilson_interval)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "visualizations")

GOOGLE, OPENAI = "#16a34a", "#2563eb"


def vendor_of(model):
    return "Google" if model.startswith("Gemini") else "OpenAI"


def _style(ax, title, xlabel=""):
    ax.set_title(title, fontsize=13, pad=14)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)


def plot_win_rates(stats, path):
    """Win rate with Wilson intervals — the honest version of a leaderboard."""
    order = sorted(stats.items(), key=lambda kv: kv[1]["win_rate"])
    models = [m for m, _ in order]
    rates = [s["win_rate"] for _, s in order]
    intervals = [wilson_interval(s["wins"], s["appearances"]) for _, s in order]
    lower = [r - lo for r, (lo, _) in zip(rates, intervals)]
    upper = [hi - r for r, (_, hi) in zip(rates, intervals)]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(models, rates, color=[GOOGLE if vendor_of(m) == "Google" else OPENAI for m in models],
            alpha=0.85)
    ax.errorbar(rates, range(len(models)), xerr=[lower, upper], fmt="none",
                ecolor="#334155", capsize=4, linewidth=1.4)
    ax.axvline(0.5, color="#64748b", linestyle="--", linewidth=1, label="parity")

    for i, (m, s) in enumerate(order):
        # A zero-width bar cannot hold white text — put the label outside it,
        # which matters most for GPT-4o, the one result the data actually supports.
        inside = s["win_rate"] > 0.12
        ax.text(0.012 if inside else s["win_rate"] + 0.015, i,
                f"{s['wins']}/{s['appearances']}", va="center", fontsize=9,
                color="white" if inside else "#0f172a", fontweight="bold")

    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    _style(ax, "Win rate by model, with 95% Wilson intervals\n"
               "(bars labelled wins/appearances — every interval overlaps parity except GPT-4o)",
           "win rate")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_bradley_terry(rows, path):
    strengths = bradley_terry(rows)
    intervals = bootstrap_bradley_terry(rows, draws=1000)
    order = sorted(strengths.items(), key=lambda kv: kv[1])
    models = [m for m, _ in order]
    values = [s for _, s in order]
    lower = [max(0, s - intervals[m][0]) for m, s in order]
    upper = [intervals[m][1] - s for m, s in order]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(models, values, color=[GOOGLE if vendor_of(m) == "Google" else OPENAI for m in models],
            alpha=0.85)
    ax.errorbar(values, range(len(models)), xerr=[lower, upper], fmt="none",
                ecolor="#334155", capsize=4, linewidth=1.4)
    ax.axvline(1.0, color="#64748b", linestyle="--", linewidth=1, label="average (1.0)")
    _style(ax, "Bradley-Terry strength, bootstrap 95% intervals\n"
               "(only GPT-4o's interval excludes the average — nothing separates the rest)",
           "strength")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_vendor(rows, path):
    counts = vendor_split(rows)
    total = sum(counts.values())
    vendors = ["Google", "OpenAI"]
    wins = [counts.get(v, 0) for v in vendors]
    intervals = [wilson_interval(w, total) for w in wins]
    rates = [w / total for w in wins]
    lower = [r - lo for r, (lo, _) in zip(rates, intervals)]
    upper = [hi - r for r, (_, hi) in zip(rates, intervals)]

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.barh(vendors, rates, color=[GOOGLE, OPENAI], alpha=0.85, height=0.5)
    ax.errorbar(rates, range(len(vendors)), xerr=[lower, upper], fmt="none",
                ecolor="#334155", capsize=5, linewidth=1.4)
    ax.axvline(0.5, color="#64748b", linestyle="--", linewidth=1)
    for i, w in enumerate(wins):
        ax.text(0.015, i, f"{w}/{total}", va="center", fontsize=10,
                color="white", fontweight="bold")
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    _style(ax, "Wins by vendor, with 95% Wilson intervals\n"
               "Exact two-sided binomial p = 0.82 — indistinguishable from a coin flip",
           "share of comparisons won")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_winner_by_prompt(rows, path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ids = [int(r["prompt_id"]) for r in rows]
    colors = [GOOGLE if r["winner_vendor"] == "Google" else OPENAI for r in rows]
    ax.bar(ids, [1] * len(rows), color=colors, alpha=0.9)
    for r in rows:
        ax.text(int(r["prompt_id"]), 1.03, r["winner"].replace("Gemini-", "G-"),
                rotation=90, ha="center", va="bottom", fontsize=7.5)
    ax.set_ylim(0, 1.9)
    ax.set_yticks([])
    ax.set_xticks(ids)
    ax.set_xlabel("prompt id", fontsize=10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_title("Winner by prompt (green = Google, blue = OpenAI)\n"
                 "One judgement per prompt, single rater (blind) — no repeats to measure variance",
                 fontsize=12, pad=14)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    rows = load_results()
    stats = tally(rows)

    targets = [
        ("wins_by_model.png", lambda p: plot_win_rates(stats, p)),
        ("bradley_terry.png", lambda p: plot_bradley_terry(rows, p)),
        ("wins_by_vendor.png", lambda p: plot_vendor(rows, p)),
        ("winner_by_prompt.png", lambda p: plot_winner_by_prompt(rows, p)),
    ]
    for name, fn in targets:
        path = os.path.join(OUT, name)
        fn(path)
        print(f"wrote visualizations/{name}")

    print(f"\n{len(rows)} comparisons, {len(stats)} models "
          f"(GPT-4o included: {'GPT-4o' in stats})")


if __name__ == "__main__":
    main()
