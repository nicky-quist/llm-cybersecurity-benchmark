#!/usr/bin/env python3
"""
CLI demo for the AI SOC Copilot.

Usage:
    python -m copilot.run_demo                 # run all sample alerts
    python -m copilot.run_demo --id ssh-brute-force   # run one sample alert
    python -m copilot.run_demo --alert path/to/alert.json   # run a custom alert

Works with no configuration: without ANTHROPIC_API_KEY set, recommendations
come from the offline synthesizer (clearly labeled in the output) instead of
a live Claude call, so this is runnable immediately after a git clone.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot import soc_copilot

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample_alerts.json")


def load_samples():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["alerts"]


def print_result(result):
    alert = result["alert"]
    print("=" * 72)
    print(f"ALERT: {alert.get('threat_type')}  [{alert.get('severity')}]  "
          f"confidence={alert.get('confidence')}%")
    print(f"MITRE: {alert.get('mitre_technique')}")
    print("-" * 72)
    print(f"Rule engine's recommendation:\n  {alert.get('recommended_action')}")
    print("-" * 72)
    print(f"AI SOC Copilot recommendation  [source: {result['recommendation_source']}]:")
    print(result["recommendation"])
    if result["cve_context"]:
        print("-" * 72)
        print("CVE context used:")
        for cve in result["cve_context"]:
            print(f"  {cve['cve_id']}: {cve['description'][:120]}")
    print("=" * 72)
    print()


def main():
    parser = argparse.ArgumentParser(description="Run the AI SOC Copilot on sample or custom alerts.")
    parser.add_argument("--id", help="Run a single sample alert by id (see sample_alerts.json).")
    parser.add_argument("--alert", help="Path to a custom alert JSON file (soc-triage-tool schema).")
    parser.add_argument("--model", default="claude-sonnet-4-5", help="Claude model to use if ANTHROPIC_API_KEY is set.")
    args = parser.parse_args()

    if args.alert:
        with open(args.alert, "r", encoding="utf-8") as f:
            alerts = [json.load(f)]
    elif args.id:
        samples = load_samples()
        alerts = [a for a in samples if a["id"] == args.id]
        if not alerts:
            print(f"No sample alert with id '{args.id}'. Available: "
                  f"{', '.join(a['id'] for a in samples)}")
            return
    else:
        alerts = load_samples()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[NOTE] ANTHROPIC_API_KEY not set — recommendations below use offline "
              "synthesis, not a live model call. Set the env var to see real Claude "
              "output.\n")

    for alert in alerts:
        result = soc_copilot.run(alert, model=args.model)
        print_result(result)


if __name__ == "__main__":
    main()
