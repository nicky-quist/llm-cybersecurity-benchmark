"""
Judge reliability: inter-rater agreement, position bias, rubric consistency.

Both rounds were judged blind to model identity, but by a single rater with no
second judge — so there is no agreement figure to report and no way to tell a
real quality difference from one judge's taste. Blinding removes the identity
bias. It does not tell you whether the judgements are reproducible. Only a second
rater does that, and this module is what turns their work into a number.

Three checks, all computed from data/judgements.csv:

  1. Cohen's kappa between each pair of judges on the pairings they both scored.
     Raw agreement is reported alongside it, because kappa alone is misleading
     when the marginals are skewed — the well-known "kappa paradox", where 90%
     agreement can produce a kappa near zero.

  2. Position bias: how often the judge picked whichever response was shown as A.
     harness/judge.py assigns A/B from a seed, so under a fair judging process
     this should sit at 50%. A significant departure means the presentation
     order is influencing verdicts, which invalidates the comparisons in a way
     no amount of blinding fixes.

  3. Rubric consistency: how often the declared winner is also the response with
     the higher rubric total. Disagreements are not errors — a judge may
     reasonably override the arithmetic — but a high rate means the rubric is not
     measuring what the judge is actually deciding on.

    python analysis/agreement.py
"""
import argparse
import collections
import csv
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JUDGEMENTS = os.path.join(ROOT, "data", "judgements.csv")

RUBRIC_KEYS = ["correctness", "completeness", "usefulness", "clarity", "grounding"]


def load_judgements(path=JUDGEMENTS):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def binomial_two_sided_p(k, n, p=0.5):
    """Exact two-sided binomial test by the method of small p-values."""
    if n == 0:
        return 1.0

    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))

    observed = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= observed * (1 + 1e-9)))


def canonical_rating(row):
    """Encode a verdict as a label that means the same thing across pairings.

    A verdict is "model X beat model Y", and X differs from row to row, so the
    raw winner name is not a category that can be compared across items. Encoding
    it as "did the alphabetically-first of the two models win?" gives a consistent
    binary label, which is what kappa needs.
    """
    pair = sorted([row["winner"], row["loser"]])
    return 1 if row["winner"] == pair[0] else 0


def cohen_kappa(pairs):
    """pairs: list of (rating_a, rating_b). Returns (kappa, raw_agreement, n)."""
    n = len(pairs)
    if n == 0:
        return None, None, 0

    agreed = sum(1 for a, b in pairs if a == b)
    po = agreed / n

    labels = {r for pair in pairs for r in pair}
    counts_a = collections.Counter(a for a, _ in pairs)
    counts_b = collections.Counter(b for _, b in pairs)
    pe = sum((counts_a[k] / n) * (counts_b[k] / n) for k in labels)

    if abs(1 - pe) < 1e-12:
        # Both judges used one label for everything. Agreement is total and kappa
        # is undefined rather than perfect — reporting 1.0 here would be a lie.
        return None, po, n
    return (po - pe) / (1 - pe), po, n


def interpret(kappa):
    if kappa is None:
        return "undefined"
    for threshold, label in ((0.81, "almost perfect"), (0.61, "substantial"),
                             (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if kappa >= threshold:
            return label
    return "worse than chance"


def agreement_report(rows):
    lines = []
    by_judge = collections.defaultdict(dict)
    for r in rows:
        by_judge[r["judge"]][r["pairing_id"]] = canonical_rating(r)

    judges = sorted(by_judge)
    lines.append(f"Judges: {', '.join(judges) if judges else 'none'}")

    if len(judges) < 2:
        lines.append("")
        lines.append("Only one judge has scored these comparisons, so there is no")
        lines.append("inter-rater agreement to report. This is the largest remaining")
        lines.append("limitation of the design: blinding removes identity bias, but a")
        lines.append("single rater's verdicts cannot be shown to be reproducible.")
        lines.append("")
        lines.append("To fix it, have a second person run:")
        lines.append("    python harness/judge.py --judge <their-name>")
        lines.append("on the same pairings, then re-run this report.")
        return lines

    lines.append("")
    lines.append("Cohen's kappa on commonly-scored pairings")
    lines.append("-" * 68)
    for a, b in itertools.combinations(judges, 2):
        shared = sorted(set(by_judge[a]) & set(by_judge[b]))
        if not shared:
            lines.append(f"{a} vs {b}: no pairings scored by both")
            continue
        kappa, po, n = cohen_kappa([(by_judge[a][p], by_judge[b][p]) for p in shared])
        kappa_text = "undefined (no marginal variation)" if kappa is None \
            else f"{kappa:.2f}  ({interpret(kappa)})"
        lines.append(f"{a} vs {b}: n = {n}, raw agreement {po:.0%}, kappa = {kappa_text}")
        if n < 20:
            lines.append(f"    n = {n} is small; this kappa is itself an unstable estimate.")
        if kappa is not None and po >= 0.8 and kappa < 0.4:
            lines.append("    High raw agreement with low kappa — the kappa paradox. Both")
            lines.append("    judges are picking one side most of the time, so chance alone")
            lines.append("    would produce most of this agreement.")
    return lines


def position_bias_report(rows):
    lines = ["", "Position bias — did the judge favour whichever response was shown first?",
             "-" * 68]
    blinded = [r for r in rows if r.get("blinded") == "yes"]
    if not blinded:
        lines.append("No blinded judgements recorded.")
        return lines

    by_judge = collections.defaultdict(list)
    for r in blinded:
        by_judge[r["judge"]].append(1 if r["winner"] == r["shown_as_a"] else 0)

    for judge, picks in sorted(by_judge.items()):
        n, a_wins = len(picks), sum(picks)
        p = binomial_two_sided_p(a_wins, n)
        verdict = "no detectable position bias" if p > 0.05 \
            else "SIGNIFICANT position bias — verdicts are tracking layout, not content"
        lines.append(f"{judge}: chose Response A in {a_wins}/{n} ({a_wins / n:.0%}), "
                     f"exact binomial p = {p:.2f}")
        lines.append(f"    {verdict}")
        if n < 20:
            lines.append(f"    n = {n} — this test has little power to detect a real bias yet.")
    return lines


def rubric_report(rows):
    lines = ["", "Rubric consistency — does the verdict follow the rubric totals?",
             "-" * 68]
    scored, mismatched, tied = 0, [], 0
    for r in rows:
        try:
            a_total = sum(int(r[f"a_{k}"]) for k in RUBRIC_KEYS)
            b_total = sum(int(r[f"b_{k}"]) for k in RUBRIC_KEYS)
        except (KeyError, ValueError):
            continue
        scored += 1
        winner_is_a = r["winner"] == r["shown_as_a"]
        if a_total == b_total:
            tied += 1
        elif (a_total > b_total) != winner_is_a:
            mismatched.append(r["pairing_id"])

    if not scored:
        lines.append("No rubric scores recorded.")
        return lines

    lines.append(f"{scored} judgement(s) with rubric scores; {len(mismatched)} where the "
                 f"declared winner scored lower ({len(mismatched) / scored:.0%})")
    if tied:
        lines.append(f"{tied} with tied rubric totals — the rubric did not separate them.")
    if mismatched:
        lines.append(f"Pairings to look at: {', '.join(mismatched[:10])}")
        lines.append("An override is legitimate; a high rate means the rubric is not")
        lines.append("capturing what the verdicts are actually being decided on.")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judgements", default=JUDGEMENTS)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows = load_judgements(args.judgements)
    if not rows:
        print("No judgements yet — data/judgements.csv does not exist or is empty.\n")
        print("It is written by harness/judge.py. Until comparisons have been judged")
        print("there is no reliability to measure.\n")
        print("    python harness/judge.py --open")
        return 0

    print(f"{len(rows)} judgement(s) recorded\n")
    for block in (agreement_report(rows), position_bias_report(rows), rubric_report(rows)):
        print("\n".join(block))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
