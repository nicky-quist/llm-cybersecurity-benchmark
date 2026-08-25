# AI SOC Copilot

An extension of this repo's LLM benchmarking work into an active tool: instead of comparing which model answers a static SOC prompt best, this pipeline uses a model to reason over a **live, structured alert** and recommend a next action.

## Why this exists

The [main benchmark](../README.md) found that different LLMs are stronger at different SOC task types, with no single model dominating. That's a useful finding for a report, but the natural next question is: **what does that look like applied to a real alert, not a static prompt?** This module answers that.

It's also a direct extension of paid work — the evaluation methodology here (structured input, retrieved context, a model call, and an explicit rationale) mirrors the rubric-based evaluation done professionally at Handshake AI, applied here to a security operations use case instead of general model benchmarking.

## Pipeline

```
soc-triage-tool alert (severity, threat_type, MITRE mapping, IOCs, ...)
        │
        ▼
attack_context.py  ── static MITRE ATT&CK technique lookup (tactic, summary, mitigations)
        │
        ▼
cve_context.py     ── live NVD lookup: explicit CVE IDs in the alert, or a keyword
        │              search when the alert type suggests exploitation
        ▼
soc_copilot.py     ── builds a grounded prompt from the alert + retrieved context
        │
        ▼
llm_client.py      ── Claude API call (ANTHROPIC_API_KEY), or a labeled offline
        │              synthesis fallback if no key is set
        ▼
Recommendation + explainability rationale
```

## Design decisions

- **Alert schema matches soc-triage-tool's output exactly** (`severity`, `threat_type`, `mitre_tactic`, `mitre_technique`, `iocs`, `recommended_action`, `confidence`, `false_positive_likelihood`, `analyst_notes`), so this can genuinely be fed alerts from that tool rather than a bespoke format built to make the demo look clean.
- **The rule engine's classification is trusted, not re-derived.** The prompt explicitly tells the model not to re-classify severity or threat type — that's soc-triage-tool's job, and it's deterministic and auditable. The model's job is the next-action recommendation and reasoning, where an LLM's flexibility actually adds value over a fixed rule table.
- **Runs with zero configuration.** Without `ANTHROPIC_API_KEY` set, every recommendation still runs end-to-end via a deterministic offline synthesizer, clearly labeled `[source: offline-synthesis]` in the output — never presented as if it came from a model. A reviewer cloning this repo doesn't need to supply an API key to see the pipeline work.
- **CVE enrichment degrades gracefully.** The NVD API call has a 6-second timeout and returns an empty result on any failure (rate limit, network issue, malformed response) rather than raising — CVE context is an enrichment, not a hard dependency.
- **Explainability is a first-class output, not an afterthought.** The prompt explicitly asks the model to name what in the alert or retrieved context drove the recommendation, and what would change it — directly informed by [DefenseStorm's "AI that's documented, governed, and explainable"](https://www.defensestorm.com/) positioning, one of the practicum-partner companies this project targets.

## Usage

```bash
# Run all sample alerts (works with no API key — offline synthesis mode)
python -m copilot.run_demo

# Run a single sample alert
python -m copilot.run_demo --id ssh-brute-force

# Run against a live Claude call
export ANTHROPIC_API_KEY=sk-...
python -m copilot.run_demo --id ssh-brute-force

# Run a custom alert (must match soc-triage-tool's output schema)
python -m copilot.run_demo --alert path/to/alert.json
```

## Limitations

- The MITRE ATT&CK context table is a curated subset covering the techniques soc-triage-tool's rule engine currently detects, not the full ATT&CK matrix.
- CVE enrichment only fires on an explicit CVE ID in the alert, or a narrow keyword match for "exploit"-type alerts — it will miss CVE-relevant context for other alert types.
- The offline synthesis fallback is deliberately plain (it does not attempt to imitate a model's reasoning style) so it's never confused with a real Claude response.
- Not yet wired to splunk-detections' live Sysmon/Windows Security telemetry — soc-triage-tool's schema is the current input contract; splunk-detections output would need a small adapter to match it.
