"""
Statistics for the pairwise benchmark.

Twenty pairwise comparisons is a small sample, and small samples produce
league tables that look decisive and are not. This module computes what the
data actually supports:

  * appearances alongside wins, because a raw win count is not comparable
    across models that were drawn a different number of times
  * Wilson score intervals on each win rate, which behave sensibly at n = 3
    and at 0/6 where the normal approximation does not
  * an exact binomial test on the vendor split, so "Google 11 - OpenAI 9"
    is reported with the probability of seeing a gap that size by chance
  * Bradley-Terry strengths, the standard model for paired-comparison data,
    with bootstrap intervals

Everything here is stdlib. The derived CSVs are regenerated from
prompt_results.csv rather than maintained by hand, which is how GPT-4o - the
only model to lose every comparison it appeared in - came to be missing from
model_wins.csv, and therefore from the results table and the dashboard chart.

    python analysis/statistics.py            # print the report
    python analysis/statistics.py --write    # also regenerate data/*.csv
"""
import argparse
import collections
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(DATA, "prompt_results.csv")

Z = 1.959964  # 95% two-sided normal quantile


def load_results(path=RESULTS):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["winner"] not in (r["model_a"], r["model_b"]):
            raise ValueError(
                f"prompt {r['prompt_id']}: winner {r['winner']!r} is not one of "
                f"the two models compared ({r['model_a']!r}, {r['model_b']!r})"
            )
    return rows


def tally(rows):
    """appearances, wins and losses per model — all three, not just wins."""
    appearances, wins = collections.Counter(), collections.Counter()
    for r in rows:
        appearances[r["model_a"]] += 1
        appearances[r["model_b"]] += 1
        wins[r["winner"]] += 1
    return {
        m: {"appearances": appearances[m], "wins": wins[m],
            "losses": appearances[m] - wins[m],
            "win_rate": wins[m] / appearances[m] if appearances[m] else 0.0}
        for m in appearances
    }


def wilson_interval(wins, n, z=Z):
    """Wilson score interval for a binomial proportion.

    Chosen over the normal approximation because that one produces intervals
    of width zero at 0/6 and 3/3, which is exactly where this dataset sits.
    """
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def binomial_two_sided_p(k, n, p=0.5):
    """Exact two-sided binomial test by the method of small p-values."""
    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))

    observed = pmf(k)
    # Floating-point slack, so outcomes as likely as the observed one are counted.
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= observed * (1 + 1e-9)))


def bradley_terry(rows, models=None, prior=0.5, iterations=1000, tol=1e-10):
    """Bradley-Terry strengths via the standard MM algorithm.

    P(i beats j) = s_i / (s_i + s_j), fitted by maximum likelihood.

    `prior` adds a half-win and half-loss for each model against a notional
    average opponent. Without it a model that lost every comparison has a
    maximum-likelihood strength of exactly zero and the fit does not converge —
    which is the situation GPT-4o is in. The prior is a documented modelling
    choice, not a neutral default, and it shrinks every estimate toward parity.
    """
    models = sorted(models or {m for r in rows for m in (r["model_a"], r["model_b"])})
    index = {m: i for i, m in enumerate(models)}
    n = len(models)

    wins = [prior] * n                 # w_i, including the prior half-win
    pair_counts = collections.Counter()
    for r in rows:
        a, b = index[r["model_a"]], index[r["model_b"]]
        pair_counts[(min(a, b), max(a, b))] += 1
        wins[index[r["winner"]]] += 1

    strengths = [1.0] * n
    for _ in range(iterations):
        updated = []
        for i in range(n):
            denom = 2 * prior / (strengths[i] + 1.0)  # the notional average opponent
            for j in range(n):
                if i == j:
                    continue
                count = pair_counts[(min(i, j), max(i, j))]
                if count:
                    denom += count / (strengths[i] + strengths[j])
            updated.append(wins[i] / denom if denom > 0 else strengths[i])

        mean = sum(updated) / n
        updated = [s / mean for s in updated]
        if max(abs(a - b) for a, b in zip(updated, strengths)) < tol:
            strengths = updated
            break
        strengths = updated

    return dict(zip(models, strengths))


def bootstrap_bradley_terry(rows, draws=2000, seed=0):
    """Resample comparisons with replacement to get intervals on the strengths."""
    rng = random.Random(seed)
    models = sorted({m for r in rows for m in (r["model_a"], r["model_b"])})
    samples = collections.defaultdict(list)

    for _ in range(draws):
        resampled = [rows[rng.randrange(len(rows))] for _ in rows]
        fitted = bradley_terry(resampled, models=models, iterations=200)
        for m in models:
            samples[m].append(fitted[m])

    out = {}
    for m in models:
        values = sorted(samples[m])
        lo = values[int(0.025 * len(values))]
        hi = values[min(len(values) - 1, int(0.975 * len(values)))]
        out[m] = (lo, hi)
    return out


def vendor_split(rows):
    counts = collections.Counter(r["winner_vendor"] for r in rows)
    return counts


def write_derived_csvs(rows, stats):
    """Regenerate the derived tables from source.

    These used to be maintained by hand, which is how a model with zero wins
    disappeared from them entirely.
    """
    model_path = os.path.join(DATA, "model_wins.csv")
    with open(model_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "appearances", "wins", "losses", "win_rate",
                    "ci_low", "ci_high"])
        for m, s in sorted(stats.items(), key=lambda kv: (-kv[1]["win_rate"], kv[0])):
            lo, hi = wilson_interval(s["wins"], s["appearances"])
            w.writerow([m, s["appearances"], s["wins"], s["losses"],
                        f"{s['win_rate']:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    vendor_path = os.path.join(DATA, "vendor_wins.csv")
    counts = vendor_split(rows)
    total = sum(counts.values())
    with open(vendor_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vendor", "wins", "comparisons", "win_rate", "ci_low", "ci_high"])
        for vendor, wins in counts.most_common():
            lo, hi = wilson_interval(wins, total)
            w.writerow([vendor, wins, total, f"{wins / total:.4f}",
                        f"{lo:.4f}", f"{hi:.4f}"])

    return model_path, vendor_path


def report(rows):
    stats = tally(rows)
    lines = []

    lines.append(f"{len(rows)} pairwise comparisons across {len(stats)} models\n")

    lines.append("Per model — win rate with 95% Wilson interval")
    lines.append(f"{'model':<24} {'app':>4} {'W':>3} {'L':>3} {'rate':>7}   95% CI")
    lines.append("-" * 66)
    for m, s in sorted(stats.items(), key=lambda kv: (-kv[1]["win_rate"], kv[0])):
        lo, hi = wilson_interval(s["wins"], s["appearances"])
        lines.append(f"{m:<24} {s['appearances']:>4} {s['wins']:>3} {s['losses']:>3} "
                     f"{s['win_rate']:>6.0%}   [{lo:.0%}, {hi:.0%}]")

    widest = max((wilson_interval(s["wins"], s["appearances"]) for s in stats.values()),
                 key=lambda ci: ci[1] - ci[0])
    lines.append(f"\nEvery interval is wide — the widest spans {widest[1] - widest[0]:.0%} "
                 f"of the range. At 3 to 7 appearances per model, that is the honest\n"
                 f"precision of this design, and the ordering above is not resolved by it.")

    counts = vendor_split(rows)
    total = sum(counts.values())
    top, top_wins = counts.most_common(1)[0]
    p = binomial_two_sided_p(top_wins, total)
    lo, hi = wilson_interval(top_wins, total)
    lines.append(f"\nVendor split")
    lines.append("-" * 66)
    for vendor, wins in counts.most_common():
        lines.append(f"{vendor:<24} {wins:>3}/{total}  ({wins / total:.0%})")
    lines.append(f"\nExact two-sided binomial test against a 50/50 null: p = {p:.3f}")
    lines.append(f"{top} win rate {top_wins}/{total} = {top_wins / total:.0%}, "
                 f"95% CI [{lo:.0%}, {hi:.0%}]")
    verdict = ("indistinguishable from chance" if p > 0.05
               else "distinguishable from chance at the 5% level")
    lines.append(f"Verdict: {verdict}. A {top_wins}-{total - top_wins} split is what a "
                 f"fair coin does routinely over {total} flips.")

    strengths = bradley_terry(rows)
    intervals = bootstrap_bradley_terry(rows)
    lines.append(f"\nBradley-Terry strengths (bootstrap 95% CI, 2000 resamples)")
    lines.append("Paired-comparison model: P(i beats j) = s_i / (s_i + s_j). 1.0 = average.")
    lines.append("-" * 66)
    for m, s in sorted(strengths.items(), key=lambda kv: -kv[1]):
        lo, hi = intervals[m]
        overlaps = "  overlaps 1.0" if lo <= 1.0 <= hi else ""
        lines.append(f"{m:<24} {s:>6.2f}   [{lo:>5.2f}, {hi:>5.2f}]{overlaps}")

    separated = [m for m, (lo, hi) in intervals.items() if not (lo <= 1.0 <= hi)]
    if separated:
        lines.append(f"\nModels whose interval excludes parity: {', '.join(sorted(separated))}")
    else:
        lines.append("\nNo model's interval excludes parity. On this evidence the pool "
                     "is not separated:\nthe data cannot rank these models.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help="regenerate data/model_wins.csv and data/vendor_wins.csv")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows = load_results()
    print(report(rows))

    if args.write:
        model_path, vendor_path = write_derived_csvs(rows, tally(rows))
        print(f"\nRegenerated {os.path.relpath(model_path, ROOT)} "
              f"and {os.path.relpath(vendor_path, ROOT)}")


if __name__ == "__main__":
    main()
