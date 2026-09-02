"""
Manual collection — for when you have no API key.

Same archive, same blind judging, same statistics as harness/collect.py. The only
difference is that the response text arrives by copy-paste from a chat UI instead
of over HTTPS, and that difference is recorded in the file's front matter rather
than papered over.

    python harness/manual.py --missing            # what still has to be collected
    python harness/manual.py --sheet              # the prompts, ready to paste out
    python harness/manual.py --add 8 GPT-5.2-High --file paste.txt
    python harness/manual.py --add 8 GPT-5.2-High     # then paste, then Ctrl-Z / Ctrl-D

A pairing becomes judgeable the moment both of its responses exist. Run
`python harness/judge.py --render` after each addition to see what has unlocked.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESPONSES = os.path.join(ROOT, "responses")

sys.path.insert(0, HERE)
from schedule import load_models, load_prompts  # noqa: E402
from judge import load_pairings  # noqa: E402

SOURCES = {
    "Anthropic": "claude.ai (model picker) or console.anthropic.com",
    "OpenAI": "chatgpt.com (model picker) or platform.openai.com",
    "Google": "gemini.google.com or aistudio.google.com",
}
NEUTRAL = "lmarena.ai — Direct Chat lets you pick a specific model, no account needed"


def path_for(prompt_id, model):
    return os.path.join(RESPONSES, str(prompt_id), f"{model}.md")


def archive(prompt, model, vendor, text, source):
    path = path_for(prompt["prompt_id"], model)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            "---\n"
            f"prompt_id: {prompt['prompt_id']}\n"
            f"category: {prompt['category']}\n"
            f"model: {model}\n"
            f"vendor: {vendor}\n"
            f"api_id: null\n"
            f"collected_utc: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            "collected_via: manual-paste\n"
            f"source: {source}\n"
            "collection_caveat: >\n"
            "  Pasted from a chat interface, not collected through the API. Chat UIs\n"
            "  apply their own system prompt, may carry conversation context, and do\n"
            "  not expose the sampling parameters, so this is not drawn under the same\n"
            "  conditions as an API response. Comparisons mixing the two carry that\n"
            "  confound; record it rather than assuming it away.\n"
            "---\n\n"
            f"## Prompt\n\n{prompt['prompt_text']}\n\n## Response\n\n{text.strip()}\n")
    return path


def missing(pairings, prompts):
    """Every (prompt, model) a scheduled pairing needs and does not have."""
    needed, unlocks = {}, {}
    for p in pairings:
        if p["prompt_id"] not in prompts:
            continue
        gaps = [m for m in (p["model_a"], p["model_b"])
                if not os.path.exists(path_for(p["prompt_id"], m))]
        for m in gaps:
            needed.setdefault((p["prompt_id"], m), []).append(p["pairing_id"])
        # A pairing one response away is the cheapest thing you can collect.
        if len(gaps) == 1:
            unlocks[(p["prompt_id"], gaps[0])] = p["pairing_id"]
    return needed, unlocks


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--missing", action="store_true", help="list what still has to be collected")
    parser.add_argument("--sheet", action="store_true", help="print the prompts to send out")
    parser.add_argument("--add", nargs=2, metavar=("PROMPT_ID", "MODEL"),
                        help="archive a response; reads --file or stdin")
    parser.add_argument("--file", help="file containing the response text")
    parser.add_argument("--source", default="", help="where it came from (recorded in front matter)")
    parser.add_argument("--pairings", help="schedule CSV")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    registry = {m["model"]: m for m in load_models()}
    prompts = {p["prompt_id"]: p for p in load_prompts()}
    pairings = load_pairings(args)

    if args.add:
        prompt_id, model = int(args.add[0]), args.add[1]
        if model not in registry:
            parser.error(f"{model!r} is not in data/models.csv")
        if prompt_id not in prompts:
            parser.error(f"no prompt {prompt_id}")
        if args.file:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        else:
            print(f"Paste the response from {model} for prompt {prompt_id}, "
                  f"then Ctrl-Z+Enter (Windows) or Ctrl-D (macOS/Linux):")
            text = sys.stdin.read()
        if not text.strip():
            parser.error("no response text given")
        path = archive(prompts[prompt_id], model, registry[model]["vendor"], text,
                       args.source or SOURCES.get(registry[model]["vendor"], "manual"))
        print(f"Archived {len(text.strip())} chars -> {os.path.relpath(path, ROOT)}")

        _, unlocks = missing(pairings, prompts)
        ready = [p for p in pairings
                 if all(os.path.exists(path_for(p["prompt_id"], m))
                        for m in (p["model_a"], p["model_b"]))]
        print(f"{len(ready)} pairing(s) now have both responses and can be judged: "
              f"python harness/judge.py --render")
        return 0

    needed, unlocks = missing(pairings, prompts)

    if args.sheet:
        by_prompt = {}
        for (prompt_id, model) in sorted(needed):
            by_prompt.setdefault(prompt_id, []).append(model)
        for prompt_id, models in sorted(by_prompt.items()):
            prompt = prompts[prompt_id]
            print("=" * 78)
            print(f"PROMPT {prompt_id} — {prompt['category']}")
            print(f"Send to: {', '.join(models)}")
            print("=" * 78)
            print(prompt["prompt_text"])
            print()
            for model in models:
                print(f"  archive with: python harness/manual.py --add {prompt_id} {model}")
            print()
        return 0

    # default / --missing
    if not needed:
        print("Nothing missing — every scheduled pairing has both responses.")
        return 0

    print(f"{len(needed)} response(s) missing across {len(pairings)} scheduled pairings.\n")
    print("Cheapest first — these each unlock a complete comparison on their own:\n")
    for (prompt_id, model), pairing_id in sorted(unlocks.items(), key=lambda kv: kv[1]):
        vendor = registry[model]["vendor"]
        print(f"  pairing {pairing_id:>3}  prompt {prompt_id:>2}  {model:<24} "
              f"[{SOURCES.get(vendor, 'manual')}]")
    print(f"\n  or use {NEUTRAL}")
    print(f"\n{len(needed) - len(unlocks)} further response(s) belong to pairings that are "
          f"missing both sides.")
    print("\nSee the prompt text with: python harness/manual.py --sheet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
