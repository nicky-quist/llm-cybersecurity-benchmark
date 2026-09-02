"""
Build a balanced pairing schedule.

The existing twenty comparisons were drawn ad hoc, and the dashboard's pairing
matrix shows what that cost: 12 of 28 possible pairings occurred, six of the
eight models were drawn too few times for any record they produced to reach
p <= 0.05, and GPT-4o happened to face a Gemini model in all six of its
comparisons. None of that is a statement about the models; it is a property of
the draw, decided before a single response was read.

This module builds the schedule up front instead, so the next round has the
power to answer something:

  * round robin *within* a tier, because a frontier-vs-lite comparison is a
    foregone conclusion that spends a judgement without buying information
  * every model appears the same number of times, so win rates are comparable
  * cross-vendor pairs are preferred when a tier has to be trimmed, since
    same-vendor pairs do not inform the vendor-level question

    python harness/schedule.py --repeats 2 > harness/pairings.csv
"""
import argparse
import csv
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def load_models(path=None):
    with open(path or os.path.join(DATA, "models.csv"), encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_prompts(path=None):
    with open(path or os.path.join(DATA, "prompt_results.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    seen, prompts = set(), []
    for r in rows:
        if r["prompt_id"] in seen:
            continue
        seen.add(r["prompt_id"])
        prompts.append({"prompt_id": int(r["prompt_id"]),
                        "category": r["category"],
                        "prompt_text": r["prompt_text"]})
    return sorted(prompts, key=lambda p: p["prompt_id"])


def tier_pairs(models, cross_vendor_only=False):
    """Every within-tier pairing, optionally restricted to cross-vendor ones."""
    by_tier = {}
    for m in models:
        by_tier.setdefault(m["tier"], []).append(m)

    pairs = []
    for tier, group in sorted(by_tier.items()):
        for a, b in itertools.combinations(sorted(group, key=lambda m: m["model"]), 2):
            if cross_vendor_only and a["vendor"] == b["vendor"]:
                continue
            pairs.append((tier, a, b))
    return pairs


def build(models, prompts, repeats=1, cross_vendor_only=False, seed=0, target=6,
          per_category=1):
    """Assign prompts to pairings, cycling so categories spread evenly.

    Each pairing is repeated `repeats` times on *different* prompts. Repeating a
    pairing at all is the point: with one comparison per pair, as in the current
    dataset, within-pair judging variance is unmeasured and every head-to-head
    'record' is a single coin flip.

    Round robin within a tier alone does not balance appearances, because the
    tiers are not the same size — six frontier models generate fifteen pairings
    while two mid-tier models generate one. So a top-up pass follows, pairing the
    two most under-represented models until everyone reaches `target`
    appearances. Six is the default because it is the smallest n at which a
    perfect record clears p <= 0.05: at five, no outcome is significant, which is
    the trap the first round of this benchmark fell into.

    `per_category` is the second trap. Round one ran twenty prompts across twenty
    categories — one observation each — which makes this project's actual research
    question ("do different models suit different SOC task types?") untestable at
    any level of care. A category with one comparison supports no claim about that
    category. Raising this to 3+ is what turns the task-specific framing from a
    hypothesis into something the data can speak to.
    """
    pairs = tier_pairs(models, cross_vendor_only)
    if not pairs:
        raise ValueError("no eligible pairings — check tiers in data/models.csv")

    rng = random.Random(seed)
    by_name = {m["model"]: m for m in models}
    appearances = {m["model"]: 0 for m in models}
    categories = sorted({p["category"] for p in prompts})
    cat_counts = {c: 0 for c in categories}
    prompt_counts = {p["prompt_id"]: 0 for p in prompts}
    schedule = []

    def next_prompt(category=None):
        """Least-used prompt from the least-covered category.

        Cycling through prompts in order spreads categories evenly only while the
        number of comparisons is a clean multiple of the number of prompts. Once
        the top-up passes start adding pairings, a plain cycle silently
        concentrates them on whichever categories happen to fall early in the
        rotation.
        """
        pool = [p for p in prompts if p["category"] == category] if category else prompts
        return min(pool, key=lambda p: (cat_counts[p["category"]],
                                        prompt_counts[p["prompt_id"]],
                                        p["prompt_id"]))

    def add(tier, a, b, category=None):
        prompt = next_prompt(category)
        cat_counts[prompt["category"]] += 1
        prompt_counts[prompt["prompt_id"]] += 1
        # Randomise which model is presented first, so presentation order is not
        # confounded with model identity before judging even starts.
        first, second = (a, b) if rng.random() < 0.5 else (b, a)
        appearances[a["model"]] += 1
        appearances[b["model"]] += 1
        schedule.append({
            "pairing_id": len(schedule) + 1,
            "tier": tier,
            "prompt_id": prompt["prompt_id"],
            "category": prompt["category"],
            "model_a": first["model"],
            "model_b": second["model"],
            "cross_vendor": "yes" if a["vendor"] != b["vendor"] else "no",
        })

    for _ in range(repeats):
        ordered = pairs[:]
        rng.shuffle(ordered)
        for tier, a, b in ordered:
            add(tier, a, b)

    # Top-up: repeatedly pair the two models furthest below target, preferring a
    # cross-vendor opponent because same-vendor pairs tell the vendor-level
    # question nothing.
    guard = 0
    while min(appearances.values()) < target and guard < 500:
        guard += 1
        short = sorted(appearances, key=lambda m: (appearances[m], m))
        a = by_name[short[0]]
        opponents = [by_name[m] for m in short[1:] if appearances[m] < target] or \
                    [by_name[m] for m in short[1:]]
        cross = [o for o in opponents if o["vendor"] != a["vendor"]]
        b = (cross or opponents)[0]
        tier = a["tier"] if a["tier"] == b["tier"] else f"{a['tier']}/{b['tier']}"
        add(tier, a, b)

    # Category top-up: bring every category up to `per_category` comparisons, so
    # per-category claims have a denominator worth quoting. Opponents are still
    # chosen by who is furthest behind, which keeps model balance while filling
    # the thin categories.
    guard = 0
    while min(cat_counts.values()) < per_category and guard < 2000:
        guard += 1
        category = min(cat_counts, key=lambda c: (cat_counts[c], c))
        short = sorted(appearances, key=lambda m: (appearances[m], m))
        a = by_name[short[0]]
        opponents = [by_name[m] for m in short[1:]]
        cross = [o for o in opponents if o["vendor"] != a["vendor"]]
        b = (cross or opponents)[0]
        tier = a["tier"] if a["tier"] == b["tier"] else f"{a['tier']}/{b['tier']}"
        add(tier, a, b, category)

    return schedule


def summarise(schedule, models):
    appearances, cat_counts = {}, {}
    for row in schedule:
        for m in (row["model_a"], row["model_b"]):
            appearances[m] = appearances.get(m, 0) + 1
        cat_counts[row["category"]] = cat_counts.get(row["category"], 0) + 1

    lines = [f"{len(schedule)} comparisons scheduled across {len(appearances)} models"]
    cross = sum(1 for r in schedule if r["cross_vendor"] == "yes")
    lines.append(f"{cross} cross-vendor ({cross / len(schedule):.0%})")
    lines.append("")
    lines.append(f"{'model':<26}{'appearances':>12}   best achievable p")
    lines.append("-" * 58)
    for m in sorted(appearances, key=lambda k: (-appearances[k], k)):
        n = appearances[m]
        best = 2 * (0.5 ** n)          # every comparison won, or every one lost
        flag = "" if best <= 0.05 else "   <- still unfalsifiable"
        lines.append(f"{m:<26}{n:>12}   {min(1.0, best):.4f}{flag}")

    thin = sorted(c for c, n in cat_counts.items() if n < 3)
    lines.append("")
    lines.append(f"{len(cat_counts)} categories, "
                 f"{min(cat_counts.values())}-{max(cat_counts.values())} comparisons each "
                 f"(mean {len(schedule) / len(cat_counts):.1f})")
    if thin:
        lines.append(f"{len(thin)} categor{'y' if len(thin) == 1 else 'ies'} below 3 "
                     f"comparisons — no per-category claim is supportable there:")
        for c in thin[:6]:
            lines.append(f"    {c} ({cat_counts[c]})")
        if len(thin) > 6:
            lines.append(f"    ... and {len(thin) - 6} more")
        lines.append("Raise with --per-category 3 (costs more comparisons, buys the "
                     "task-specific question).")
    else:
        lines.append("Every category has at least 3 comparisons — the task-specific "
                     "question is answerable at this design.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=2,
                        help="times each pairing is run, on different prompts (default 2)")
    parser.add_argument("--cross-vendor-only", action="store_true",
                        help="drop same-vendor pairings")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=int, default=6,
                        help="minimum appearances per model (default 6 — the smallest "
                             "n at which a perfect record reaches p <= 0.05)")
    parser.add_argument("--per-category", type=int, default=1,
                        help="minimum comparisons per category (default 1). Use 3+ to "
                             "make per-category claims supportable — round one had 1, "
                             "which is why its task-specific framing stayed a hypothesis")
    parser.add_argument("--out", help="write CSV here instead of stdout")
    parser.add_argument("--summary", action="store_true",
                        help="print the power summary to stderr instead of a schedule")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    models = [m for m in load_models() if m["vendor"]]
    schedule = build(models, load_prompts(), args.repeats,
                     args.cross_vendor_only, args.seed, args.target,
                     args.per_category)

    if args.summary:
        print(summarise(schedule, models))
        return 0

    fields = ["pairing_id", "tier", "prompt_id", "category",
              "model_a", "model_b", "cross_vendor"]
    target = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(schedule)
    finally:
        if args.out:
            target.close()
            print(summarise(schedule, models), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
