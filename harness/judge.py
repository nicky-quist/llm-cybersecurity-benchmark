"""
Blind pairwise judging.

The original round was judged blind — Handshake AI Versus withheld the model
names until the verdict was in — but it kept no record of which response was
shown first and no rubric, so its verdicts can be neither position-bias-checked
nor decomposed.

This harness keeps the blinding and adds both. For each pairing it renders the
two archived responses side by side as "Response A" and "Response B", with the
model names withheld, in an order decided by a seed rather than by the schedule.
The mapping is written to data/judgements.csv only after the verdict is recorded,
so it cannot leak into the judgement, and the seed makes the whole run
reproducible.

    python harness/judge.py --render            # write the blind pages + index
    python harness/judge.py --import FILE       # ingest verdicts from those pages
    python harness/judge.py                     # or judge in the terminal instead
    python harness/judge.py --append            # also append to prompt_results.csv

Judging happens in the browser by default: --render writes an index plus one page
per comparison, each with the two responses side by side and the verdict controls
beneath them. Verdicts sit in the browser's localStorage until exported, so a
session can be picked up later, and --import resolves the exported A/B choices to
model names here rather than in the page.

Judging remains a human job here on purpose. Having a model score a comparison
that includes its own output is self-preference bias, and it is exactly the kind
of shortcut this repository's README is about not taking.
"""
import argparse
import csv
import json
import os
import random
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RESPONSES = os.path.join(ROOT, "responses")
BLIND = os.path.join(HERE, "blind")

sys.path.insert(0, HERE)
import blind_page  # noqa: E402
from schedule import build, load_models, load_prompts  # noqa: E402

RUBRIC = [
    ("correctness", "technically correct — no wrong facts, commands or field names"),
    ("completeness", "covers what a SOC analyst actually needs, not just the obvious half"),
    ("usefulness", "operationally usable as written, in a real SOC"),
    ("clarity", "structured so it can be acted on under time pressure"),
    ("grounding", "resists inventing incidents, CVEs, log fields or product features"),
]

JUDGEMENTS = os.path.join(DATA, "judgements.csv")
RESULTS = os.path.join(DATA, "prompt_results.csv")


def read_response(prompt_id, model):
    path = os.path.join(RESPONSES, str(prompt_id), f"{model}.md")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # Strip the front matter, which names the model — the whole point is that
    # the judge does not see it.
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2] if len(parts) > 2 else text
    marker = "## Response"
    return text.split(marker, 1)[1].strip() if marker in text else text.strip()


def blind_order(pairing_id, seed):
    """Which model is shown as A. Decided by seed, not by the schedule order."""
    return random.Random(f"{seed}:{pairing_id}").random() < 0.5


def load_pairings(args):
    path = args.pairings or os.path.join(HERE, "pairings.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            return [dict(r, pairing_id=int(r["pairing_id"]), prompt_id=int(r["prompt_id"]))
                    for r in csv.DictReader(f)]
    models = load_models()
    return build(models, load_prompts(), repeats=args.repeats, seed=args.seed)


def render_page(pairing, prompt, a_text, b_text, prev_id=None, next_id=None):
    """Write one blind side-by-side page.

    The page shows Response A and Response B and never learns which model wrote
    either. It records a verdict of "a" or "b" against the pairing id; the mapping
    back to model names lives here, keyed by the same seed that decided the
    presentation order. That separation is what makes the blinding real rather
    than cosmetic: there is nothing in the delivered HTML to inspect.
    """
    os.makedirs(BLIND, exist_ok=True)
    path = os.path.join(BLIND, f"pairing-{pairing['pairing_id']:03d}.html")
    return blind_page.render_comparison(path, pairing, prompt, a_text, b_text,
                                        RUBRIC, prev_id, next_id)


def ask(prompt_text, valid=None):
    while True:
        answer = input(prompt_text).strip()
        if valid is None and answer:
            return answer
        if valid and answer.lower() in valid:
            return answer.lower()
        print(f"  expected one of: {', '.join(valid)}" if valid else "  answer required")


def score_block(label):
    print(f"\n  Rubric for Response {label} (1-5, blank = 3):")
    scores = {}
    for key, description in RUBRIC:
        raw = input(f"    {key:<13} {description}\n    > ").strip()
        scores[key] = int(raw) if raw.isdigit() and 1 <= int(raw) <= 5 else 3
    return scores


def already_judged():
    if not os.path.exists(JUDGEMENTS):
        return set()
    with open(JUDGEMENTS, encoding="utf-8-sig") as f:
        return {int(r["pairing_id"]) for r in csv.DictReader(f)}


def append_row(path, fields, row):
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def record_verdict(p, prompt, choice, scores_a, scores_b, rationale,
                   registry, seed, judge, round_label, append, blinded="yes"):
    """Turn an A/B verdict into rows, resolving the blind labels to model names.

    This is the only place the mapping happens, and it happens after the verdict
    exists — which is what keeps the blinding meaningful. Shared by the terminal
    flow and the --import flow so the two cannot drift.

    `blinded` records whether the judge actually could not see model identities
    when deciding. It is a property of how the verdict was produced, not a setting
    — the position-bias and agreement statistics in analysis/agreement.py read it,
    so recording it wrongly corrupts those rather than just mislabelling a row.
    """
    first = blind_order(p["pairing_id"], seed)
    shown_a = p["model_a"] if first else p["model_b"]
    shown_b = p["model_b"] if first else p["model_a"]
    winner = shown_a if choice == "a" else shown_b
    loser = shown_b if choice == "a" else shown_a

    append_row(JUDGEMENTS,
               ["pairing_id", "prompt_id", "category", "shown_as_a", "shown_as_b",
                "winner", "loser", "winner_vendor", "judge", "blinded", "rationale"]
               + [f"a_{k}" for k, _ in RUBRIC] + [f"b_{k}" for k, _ in RUBRIC],
               {"pairing_id": p["pairing_id"], "prompt_id": p["prompt_id"],
                "category": p["category"], "shown_as_a": shown_a, "shown_as_b": shown_b,
                "winner": winner, "loser": loser,
                "winner_vendor": registry[winner]["vendor"], "judge": judge,
                "blinded": blinded, "rationale": rationale,
                **{f"a_{k}": scores_a.get(k, "") for k, _ in RUBRIC},
                **{f"b_{k}": scores_b.get(k, "") for k, _ in RUBRIC}})

    if append:
        append_row(RESULTS,
                   ["prompt_id", "category", "prompt_text", "model_a", "model_b",
                    "winner", "winner_vendor", "loser", "rationale", "round"],
                   {"prompt_id": p["prompt_id"], "category": p["category"],
                    "prompt_text": prompt["prompt_text"],
                    "model_a": p["model_a"], "model_b": p["model_b"],
                    "winner": winner, "winner_vendor": registry[winner]["vendor"],
                    "loser": loser, "rationale": rationale, "round": round_label})
    return winner, loser


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pairings", help="schedule CSV (default harness/pairings.csv, else generated)")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0, help="seed for the blind A/B assignment")
    parser.add_argument("--render", action="store_true",
                        help="write the blind pages plus an index, and stop")
    parser.add_argument("--import", dest="import_file", metavar="FILE",
                        help="ingest verdicts exported from the browser judging pages")
    parser.add_argument("--open", action="store_true", help="open each page in a browser while judging")
    parser.add_argument("--append", action="store_true",
                        help="also append verdicts to data/prompt_results.csv")
    parser.add_argument("--judge", default=os.environ.get("USERNAME") or "unknown",
                        help="judge identifier recorded with each verdict")
    parser.add_argument("--blinded", choices=("yes", "no"), default="yes",
                        help="was the judge blind to model identity when deciding? "
                             "analysis/agreement.py reads this for the position-bias "
                             "test, so a wrong value corrupts a statistic")
    parser.add_argument("--round", default="2",
                        help="round label written to prompt_results.csv (default 2). "
                             "Round 1 is the original Handshake Versus data (blind, but "
                             "no archived responses or rubric); keeping them separable is "
                             "the point of the column.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    registry = {m["model"]: m for m in load_models()}
    prompts = {p["prompt_id"]: p for p in load_prompts()}
    pairings = load_pairings(args)
    seen = already_judged()

    ready, missing = [], []
    for p in pairings:
        prompt = prompts.get(p["prompt_id"])
        if not prompt:
            continue
        a = read_response(p["prompt_id"], p["model_a"])
        b = read_response(p["prompt_id"], p["model_b"])
        if a is None or b is None:
            gaps = [m for m, t in ((p["model_a"], a), (p["model_b"], b)) if t is None]
            missing.append(f"pairing {p['pairing_id']} (prompt {p['prompt_id']}): "
                           f"no archived response for {', '.join(gaps)}")
            continue
        ready.append((p, prompt, a, b))

    print(f"{len(pairings)} pairings scheduled, {len(ready)} have both responses archived, "
          f"{len(seen)} already judged")
    if missing:
        print(f"{len(missing)} waiting on harness/collect.py:")
        for note in missing[:8]:
            print(f"  {note}")
        if len(missing) > 8:
            print(f"  ... and {len(missing) - 8} more")

    if args.render:
        ids = [p["pairing_id"] for p, _, _, _ in ready]
        for i, (p, prompt, a, b) in enumerate(ready):
            first = blind_order(p["pairing_id"], args.seed)
            render_page(p, prompt, a if first else b, b if first else a,
                        prev_id=ids[i - 1] if i else None,
                        next_id=ids[i + 1] if i + 1 < len(ids) else None)
        index = blind_page.render_index(os.path.join(BLIND, "index.html"),
                                        [p for p, _, _, _ in ready])
        print(f"\n{len(ready)} page(s) written. Start here:")
        print(f"  {os.path.relpath(index, ROOT)}")
        print("\nJudge in the browser, click Export verdicts, save the JSON, then:")
        print("  python harness/judge.py --import harness/verdicts.json --append")
        return 0

    if args.import_file:
        # utf-8-sig, not utf-8: the export is copied out of a browser and saved by
        # hand, and Windows editors (PowerShell's Set-Content included) write a
        # BOM that json.load rejects outright.
        with open(args.import_file, encoding="utf-8-sig") as f:
            verdicts = json.load(f)
        by_id = {p["pairing_id"]: (p, prompt) for p, prompt, _, _ in ready}
        imported, skipped = 0, []
        for v in verdicts:
            pid = int(v["pairing_id"])
            if pid in seen:
                skipped.append(f"pairing {pid}: already in judgements.csv")
                continue
            if pid not in by_id:
                skipped.append(f"pairing {pid}: not a pairing with both responses archived")
                continue
            if v.get("choice") not in ("a", "b"):
                skipped.append(f"pairing {pid}: no verdict")
                continue
            p, prompt = by_id[pid]
            winner, loser = record_verdict(
                p, prompt, v["choice"], v.get("a", {}), v.get("b", {}),
                v.get("rationale", ""), registry, args.seed, args.judge,
                args.round, args.append, args.blinded)
            print(f"  pairing {pid}: {winner} beat {loser}")
            imported += 1
        print(f"\n{imported} verdict(s) imported"
              + (f", {len(skipped)} skipped" if skipped else ""))
        for note in skipped:
            print(f"  {note}")
        if imported:
            print("\nNext:")
            print("  python analysis/agreement.py")
            print("  python analysis/statistics.py --write")
            print("  python analysis/build_dashboard.py")
        return 0

    todo = [r for r in ready if r[0]["pairing_id"] not in seen]
    if not todo:
        print("\nNothing left to judge.")
        return 0

    for p, prompt, a_resp, b_resp in todo:
        first = blind_order(p["pairing_id"], args.seed)
        page = render_page(p, prompt, a_resp if first else b_resp, b_resp if first else a_resp)

        print("\n" + "=" * 74)
        print(f"Pairing {p['pairing_id']} · prompt {p['prompt_id']} · {p['category']}")
        print("=" * 74)
        print(f"\n{prompt['prompt_text']}\n")
        print(f"Side by side: {os.path.relpath(page, ROOT)}")
        if args.open:
            webbrowser.open(f"file://{page}")

        winner_label = ask("\n  Which response is better? [a/b/skip] ", {"a", "b", "skip"})
        if winner_label == "skip":
            continue

        scores_a = score_block("A")
        scores_b = score_block("B")
        rationale = ask("\n  One line — what decided it?\n  > ")

        winner, loser = record_verdict(
            p, prompt, winner_label, scores_a, scores_b, rationale,
            registry, args.seed, args.judge, args.round, args.append, args.blinded)
        print(f"\n  Recorded: {winner} beat {loser}  (Response "
              f"{'A' if winner_label == 'a' else 'B'} was {winner})")

    print("\nDone. Next:")
    print("  python analysis/statistics.py --write")
    print("  python analysis/build_dashboard.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
