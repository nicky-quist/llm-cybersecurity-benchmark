"""
AI SOC Copilot — the core pipeline.

Takes a triage result in soc-triage-tool's output schema (severity,
threat_type, mitre_tactic, mitre_technique, iocs, recommended_action,
confidence, false_positive_likelihood, analyst_notes) and produces a
next-action recommendation grounded in MITRE ATT&CK + CVE/NVD context, plus
an explicit explainability write-up describing why the model made that call.

This extends llm-cybersecurity-benchmark's pairwise LLM evaluation work
(see ../README.md and ../methodology.md) into an active tool: instead of
comparing which model answers a static SOC prompt best, this pipeline uses
a model to reason over a live, structured alert.
"""

from . import attack_context
from . import cve_context
from . import llm_client

PROMPT_TEMPLATE = """You are a SOC analyst copilot. You are given a structured alert that has already been triaged by a deterministic rule engine, plus MITRE ATT&CK and CVE context retrieved automatically. Your job is NOT to re-classify the alert — trust the given severity, threat_type, and MITRE mapping. Instead:

1. Recommend a concrete next action for the on-call analyst, more specific than the rule engine's generic recommendation.
2. Explain your reasoning in 2-3 sentences: what in the alert data and the retrieved context most influenced this recommendation, and what would change your recommendation (e.g. a different IOC, a different CVSS score).
3. Flag anything in the context that seems inconsistent or worth double-checking before acting.

Be concise and operational — this is read by an analyst mid-incident, not a report.

ALERT:
- Threat type: {threat_type}
- Severity: {severity}
- Confidence: {confidence}%
- False positive likelihood: {false_positive_likelihood}
- MITRE tactic / technique: {mitre_tactic} / {mitre_technique}
- Indicators of compromise: {iocs}
- Rule engine's recommended action: {recommended_action}
- Analyst notes: {analyst_notes}

MITRE ATT&CK CONTEXT:
{attack_context_block}

CVE CONTEXT:
{cve_context_block}
"""


def _format_attack_context(ctx):
    if not ctx:
        return "No specific technique context retrieved."
    lines = [f"{ctx['name']} ({ctx['tactic']}): {ctx['summary']}"]
    if ctx.get("typical_mitigations"):
        lines.append("Typical mitigations: " + "; ".join(ctx["typical_mitigations"]))
    return "\n".join(lines)


def _format_cve_context(cves):
    if not cves:
        return "No related CVEs identified in this alert."
    lines = []
    for cve in cves:
        sev = f" (CVSS {cve['cvss_score']}, {cve['cvss_severity']})" if cve.get("cvss_score") else ""
        lines.append(f"{cve['cve_id']}{sev}: {cve['description']}")
    return "\n".join(lines)


def run(alert, model="claude-sonnet-4-5"):
    """
    alert: dict matching soc-triage-tool's analyzeOffline() output schema.
    Returns a dict with the enrichment context, the LLM's recommendation,
    and metadata about how the recommendation was produced (explainability).
    """
    attack_ctx = attack_context.lookup(alert.get("mitre_technique", ""))

    alert_text = " ".join([
        alert.get("summary", ""),
        alert.get("threat_type", ""),
        " ".join(alert.get("iocs", []) or []),
    ])
    cve_ctx = cve_context.enrich(alert_text, threat_type=alert.get("threat_type", ""))

    prompt = PROMPT_TEMPLATE.format(
        threat_type=alert.get("threat_type", "Unknown"),
        severity=alert.get("severity", "UNKNOWN"),
        confidence=alert.get("confidence", "?"),
        false_positive_likelihood=alert.get("false_positive_likelihood", "Unknown"),
        mitre_tactic=alert.get("mitre_tactic", "Unknown"),
        mitre_technique=alert.get("mitre_technique", "Unknown"),
        iocs=", ".join(alert.get("iocs", []) or []) or "none extracted",
        recommended_action=alert.get("recommended_action", ""),
        analyst_notes=alert.get("analyst_notes", "") or "none",
        attack_context_block=_format_attack_context(attack_ctx),
        cve_context_block=_format_cve_context(cve_ctx),
    )

    response = llm_client.get_recommendation(prompt, alert, attack_ctx, cve_ctx, model=model)

    return {
        "alert": alert,
        "attack_context": attack_ctx,
        "cve_context": cve_ctx,
        "recommendation": response.text,
        "recommendation_source": response.source,
        "prompt_used": prompt,
    }
