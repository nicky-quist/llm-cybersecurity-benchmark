"""
Pluggable LLM client for the AI SOC Copilot.

Uses the Claude API (via ANTHROPIC_API_KEY) when available. If the key isn't
set, or the anthropic package isn't installed, falls back to a clearly-labeled
offline synthesizer that assembles a recommendation from the enrichment
context directly — no fabricated model output. This mirrors soc-triage-tool's
own "offline-first, no third-party API required to run" design, so this repo
is reviewable without anyone needing to supply an API key.
"""

import os


class LLMResponse:
    def __init__(self, text, source):
        self.text = text
        self.source = source  # "claude" or "offline-synthesis"


def _call_claude(prompt, model="claude-sonnet-4-5"):
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def _offline_synthesis(alert, attack_ctx, cve_ctx):
    """
    Deterministic fallback: same information the LLM prompt would have received,
    assembled into readable prose without a model call. Explicitly labeled as
    offline synthesis in the output so it's never mistaken for a model response.
    """
    lines = []
    lines.append(f"Threat: {alert.get('threat_type', 'Unknown')} "
                  f"({alert.get('severity', 'UNKNOWN')} severity, "
                  f"{alert.get('confidence', '?')}% confidence).")

    if attack_ctx:
        lines.append(f"MITRE mapping: {alert.get('mitre_technique', 'Unknown')} "
                      f"under the {attack_ctx['tactic']} tactic — {attack_ctx['summary']}")
        if attack_ctx.get("typical_mitigations"):
            lines.append("Standard mitigations for this technique: "
                          + "; ".join(attack_ctx["typical_mitigations"]) + ".")

    if cve_ctx:
        for cve in cve_ctx:
            sev = f" (CVSS {cve['cvss_score']}, {cve['cvss_severity']})" if cve.get("cvss_score") else ""
            lines.append(f"Related vulnerability {cve['cve_id']}{sev}: {cve['description']}")

    lines.append(f"Recommended action: {alert.get('recommended_action', 'Investigate further.')}")
    return "\n".join(lines)


def get_recommendation(prompt, alert, attack_ctx, cve_ctx, model="claude-sonnet-4-5"):
    """
    Returns an LLMResponse. Tries the Claude API first; falls back to offline
    synthesis on any error (missing key, missing package, network failure, etc.)
    so the pipeline always produces output.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            text = _call_claude(prompt, model=model)
            return LLMResponse(text=text, source="claude")
        except Exception as exc:
            fallback = _offline_synthesis(alert, attack_ctx, cve_ctx)
            note = f"[Claude API call failed ({exc.__class__.__name__}); using offline synthesis]\n\n"
            return LLMResponse(text=note + fallback, source="offline-synthesis")

    fallback = _offline_synthesis(alert, attack_ctx, cve_ctx)
    note = "[No ANTHROPIC_API_KEY set; using offline synthesis instead of a live model call]\n\n"
    return LLMResponse(text=note + fallback, source="offline-synthesis")
