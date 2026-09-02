"""
Inject the source CSVs into dashboard/index.html.

The dashboard used to carry its own hand-pasted copy of the twenty comparisons.
That copy had drifted from data/prompt_results.csv — the categories had been
title-cased into things like "Soc Detection" and "Ai For Cybersecurity" — and a
hand-maintained copy is the same failure mode that once dropped GPT-4o, the only
model with a significant result, out of the reported tables entirely.

So the page now carries a generated block between two markers, and this script
is the only thing allowed to write it. tests/test_dashboard_data.py asserts the
block still matches the CSVs, so the two cannot drift again silently.

    python analysis/build_dashboard.py           # rewrite the block
    python analysis/build_dashboard.py --check   # exit 1 if it is stale
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(DATA, "prompt_results.csv")
MODELS = os.path.join(DATA, "models.csv")
DASHBOARD = os.path.join(ROOT, "dashboard", "index.html")

START = "// <<<GENERATED-DATA — do not edit by hand; run: python analysis/build_dashboard.py"
END = "// GENERATED-DATA>>>"

# `round` separates the original Handshake Versus comparisons (round 1 — blind,
# but no archived responses, no rubric, ad-hoc pairings) from harness-collected
# ones (round 2 — blind A/B, responses on disk, computed schedule). Mixing them
# silently would launder round one's limitations into the newer data, so the
# column travels with every row.
COMPARISON_FIELDS = ["prompt_id", "category", "prompt_text",
                     "model_a", "model_b", "winner", "rationale", "round"]


def load_models(path=MODELS):
    with open(path, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_comparisons(path=RESULTS):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        row = {k: r[k] for k in COMPARISON_FIELDS if k in r}
        row["prompt_id"] = int(row["prompt_id"])
        out.append(row)
    return out


def validate(models, comparisons):
    """Fail loudly rather than shipping a page that mislabels a vendor.

    The dashboard derives a model's vendor from models.csv. A model that
    appears in a comparison but not in the registry would silently render as
    vendor "Unknown", which is exactly the class of quiet mislabelling this
    project has already been bitten by once.
    """
    registered = {m["model"] for m in models}
    problems = []

    for r in comparisons:
        for field in ("model_a", "model_b"):
            if r[field] not in registered:
                problems.append(
                    f"prompt {r['prompt_id']}: {r[field]!r} is not in data/models.csv"
                )
        if r["winner"] not in (r["model_a"], r["model_b"]):
            problems.append(
                f"prompt {r['prompt_id']}: winner {r['winner']!r} is not one of the "
                f"two models compared ({r['model_a']!r}, {r['model_b']!r})"
            )

    for m in models:
        if m["vendor"] not in ("Google", "OpenAI", "Anthropic"):
            problems.append(
                f"{m['model']}: vendor {m['vendor']!r} has no brand colours defined in "
                f"dashboard/index.html — add --v-{m['vendor']}, --v-{m['vendor']}-2 "
                f"and --v-{m['vendor']}-soft first"
            )
        if m["status"] not in ("evaluated", "planned"):
            problems.append(f"{m['model']}: status must be 'evaluated' or 'planned'")

    appeared = {m for r in comparisons for m in (r["model_a"], r["model_b"])}
    for m in models:
        expected = "evaluated" if m["model"] in appeared else "planned"
        if m["status"] != expected:
            problems.append(
                f"{m['model']}: status is {m['status']!r} but it appears in "
                f"{'some' if m['model'] in appeared else 'no'} comparisons "
                f"(expected {expected!r})"
            )

    if problems:
        raise ValueError("data/models.csv and data/prompt_results.csv disagree:\n  - "
                         + "\n  - ".join(problems))


def render_block(models, comparisons):
    def dumps(rows):
        return "[\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows) + "\n]"

    return (
        f"{START}\n"
        f"const MODELS = {dumps(models)};\n"
        f"const COMPARISONS = {dumps(comparisons)};\n"
        f"{END}"
    )


def splice(html, block):
    start = html.index(START)
    end = html.index(END) + len(END)
    return html[:start] + block + html[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="verify the embedded block is current; exit 1 if not")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    models = load_models()
    comparisons = load_comparisons()
    validate(models, comparisons)

    with open(DASHBOARD, encoding="utf-8") as f:
        html = f.read()

    updated = splice(html, render_block(models, comparisons))

    if args.check:
        if updated != html:
            print("dashboard/index.html is stale — run: python analysis/build_dashboard.py")
            return 1
        print("dashboard/index.html is in sync with data/")
        return 0

    if updated == html:
        print("dashboard/index.html already in sync — nothing to do")
        return 0

    with open(DASHBOARD, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    print(f"Wrote {len(comparisons)} comparisons and {len(models)} models "
          f"into dashboard/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
