"""
Collect model responses and archive them.

The single biggest limitation of the original twenty comparisons is that the raw
model outputs were never saved, so no judgement can be independently re-scored
and nobody else can check the work. This script fixes that at the source: every
response is written to responses/<prompt_id>/<model>.md with the request
parameters in its front matter, before any judging happens.

Zero dependencies — stdlib urllib, same as the rest of the analysis code.

    set ANTHROPIC_API_KEY=...      (or export, on a POSIX shell)
    set OPENAI_API_KEY=...
    set GOOGLE_API_KEY=...

    python harness/collect.py --models Claude-Opus-5 --dry-run
    python harness/collect.py --models Claude-Opus-5,Claude-Sonnet-5

Only models whose vendor key is present are attempted; the rest are reported as
skipped rather than failing the run, so you can collect one vendor at a time.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESPONSES = os.path.join(ROOT, "responses")

sys.path.insert(0, HERE)
from schedule import load_models, load_prompts  # noqa: E402

# Display name -> the id the provider's API actually expects. Verify these
# against each provider's current model list before a run; providers rename and
# retire ids, and a stale id fails with a 404 that says very little.
API_IDS = {
    "Claude-Opus-5": "claude-opus-5",
    "Claude-Sonnet-5": "claude-sonnet-5",
    "Claude-Haiku-4.5": "claude-haiku-4-5-20251001",
    "GPT-5.2": "gpt-5.2",
    "GPT-5.2-High": "gpt-5.2",
    "GPT-4o": "gpt-4o",
    "GPT-4.1-Mini": "gpt-4.1-mini",
    "Gemini-2.5-Pro": "gemini-2.5-pro",
    "Gemini-2.5-Flash-Lite": "gemini-2.5-flash-lite",
    "Gemini-3-Flash-Preview": "gemini-3-flash-preview",
    "Gemini-3.1-Pro-Preview": "gemini-3.1-pro-preview",
}

ENV_KEYS = {
    "Anthropic": "ANTHROPIC_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Google": "GOOGLE_API_KEY",
}

MAX_TOKENS = 2000


def post(url, payload, headers, timeout=120):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def call_anthropic(api_id, prompt, key):
    body = post("https://api.anthropic.com/v1/messages",
                {"model": api_id, "max_tokens": MAX_TOKENS,
                 "messages": [{"role": "user", "content": prompt}]},
                {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in body.get("content", []))


def call_openai(api_id, prompt, key):
    body = post("https://api.openai.com/v1/chat/completions",
                {"model": api_id, "max_completion_tokens": MAX_TOKENS,
                 "messages": [{"role": "user", "content": prompt}]},
                {"Authorization": f"Bearer {key}"})
    return body["choices"][0]["message"]["content"]


def call_google(api_id, prompt, key):
    body = post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{api_id}:generateContent",
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"maxOutputTokens": MAX_TOKENS}},
        {"x-goog-api-key": key})
    parts = body["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


CLIENTS = {"Anthropic": call_anthropic, "OpenAI": call_openai, "Google": call_google}


def response_path(prompt_id, model):
    return os.path.join(RESPONSES, str(prompt_id), f"{model}.md")


def archive(prompt, model, vendor, api_id, text):
    path = response_path(prompt["prompt_id"], model)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            "---\n"
            f"prompt_id: {prompt['prompt_id']}\n"
            f"category: {prompt['category']}\n"
            f"model: {model}\n"
            f"vendor: {vendor}\n"
            f"api_id: {api_id}\n"
            f"max_tokens: {MAX_TOKENS}\n"
            f"collected_utc: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            "---\n\n"
            f"## Prompt\n\n{prompt['prompt_text']}\n\n## Response\n\n{text}\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", help="comma-separated display names (default: every model in models.csv)")
    parser.add_argument("--prompts", help="comma-separated prompt ids (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="show the plan, make no API calls")
    parser.add_argument("--overwrite", action="store_true", help="re-collect responses already on disk")
    parser.add_argument("--sleep", type=float, default=0.5, help="seconds between calls")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    registry = {m["model"]: m for m in load_models()}
    wanted = [m.strip() for m in args.models.split(",")] if args.models else list(registry)
    unknown = [m for m in wanted if m not in registry]
    if unknown:
        parser.error(f"not in data/models.csv: {', '.join(unknown)}")

    prompts = load_prompts()
    if args.prompts:
        keep = {int(p) for p in args.prompts.split(",")}
        prompts = [p for p in prompts if p["prompt_id"] in keep]

    planned, skipped, done, failed = [], [], [], []
    for model in wanted:
        vendor = registry[model]["vendor"]
        key = os.environ.get(ENV_KEYS.get(vendor, ""), "")
        if not key:
            skipped.append(f"{model}: no {ENV_KEYS.get(vendor, '?')} in the environment")
            continue
        if model not in API_IDS:
            skipped.append(f"{model}: no API id mapped in harness/collect.py")
            continue
        for prompt in prompts:
            if not args.overwrite and os.path.exists(response_path(prompt["prompt_id"], model)):
                continue
            planned.append((prompt, model, vendor, key))

    print(f"{len(planned)} responses to collect "
          f"({len(prompts)} prompts x {len(wanted)} models, minus what is already archived)")
    for note in skipped:
        print(f"  skipped — {note}")

    if args.dry_run or not planned:
        return 0

    for i, (prompt, model, vendor, key) in enumerate(planned, 1):
        api_id = API_IDS[model]
        label = f"[{i}/{len(planned)}] prompt {prompt['prompt_id']} -> {model}"
        try:
            text = CLIENTS[vendor](api_id, prompt["prompt_text"], key)
            path = archive(prompt, model, vendor, api_id, text)
            done.append(path)
            print(f"{label}: {len(text)} chars -> {os.path.relpath(path, ROOT)}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            failed.append(f"{model}/{prompt['prompt_id']}: HTTP {e.code} {detail}")
            print(f"{label}: FAILED HTTP {e.code}")
        except Exception as e:                                  # noqa: BLE001
            failed.append(f"{model}/{prompt['prompt_id']}: {e}")
            print(f"{label}: FAILED {e}")
        time.sleep(args.sleep)

    print(f"\n{len(done)} archived, {len(failed)} failed")
    for note in failed:
        print(f"  {note}")
    if done:
        print("\nNext: python harness/judge.py --blind")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
