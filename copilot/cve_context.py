"""
CVE enrichment via the public NVD REST API.

Two lookup paths:
  - lookup_by_id: an explicit CVE-YYYY-NNNNN found in the alert text
  - search_by_keyword: a short keyword (e.g. a product name pulled from an
    "Exploit Public-Facing Application" alert) when no explicit CVE is present

Network calls degrade gracefully — a timeout, non-200, or malformed response
returns an empty result rather than raising, since CVE context is an
enrichment, not a hard dependency for the pipeline to run.
"""

import json
import re
import urllib.request
import urllib.parse

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CVE_ID_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
TIMEOUT_SECONDS = 6


def extract_cve_ids(text):
    """Pull any explicit CVE IDs out of free text (e.g. an alert signature or IOC list)."""
    if not text:
        return []
    seen = []
    for match in CVE_ID_RE.findall(text):
        upper = match.upper()
        if upper not in seen:
            seen.append(upper)
    return seen


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-soc-copilot/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        if resp.status != 200:
            return None
        return json.loads(resp.read().decode("utf-8"))


def lookup_by_id(cve_id):
    """Fetch a single CVE's summary + CVSS score from NVD. Returns None on any failure."""
    try:
        url = f"{NVD_BASE}?cveId={urllib.parse.quote(cve_id)}"
        data = _fetch(url)
        vulns = data.get("vulnerabilities") if data else None
        if not vulns:
            return None
        cve = vulns[0]["cve"]
        return _summarize(cve)
    except Exception:
        return None


def search_by_keyword(keyword, max_results=3):
    """Search NVD for CVEs matching a keyword (e.g. a product/vendor name). Returns [] on failure."""
    if not keyword:
        return []
    try:
        url = f"{NVD_BASE}?keywordSearch={urllib.parse.quote(keyword)}&resultsPerPage={max_results}"
        data = _fetch(url)
        vulns = data.get("vulnerabilities") if data else None
        if not vulns:
            return []
        return [_summarize(v["cve"]) for v in vulns[:max_results]]
    except Exception:
        return []


def _summarize(cve):
    cve_id = cve.get("id", "unknown")
    descriptions = cve.get("descriptions", [])
    description = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

    cvss_score = None
    cvss_severity = None
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if key in metrics and metrics[key]:
            cvss_data = metrics[key][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            cvss_severity = metrics[key][0].get("baseSeverity") or cvss_data.get("baseSeverity")
            break

    return {
        "cve_id": cve_id,
        "description": description[:400],
        "cvss_score": cvss_score,
        "cvss_severity": cvss_severity,
    }


def enrich(alert_text, threat_type=""):
    """
    Best-effort CVE context for an alert: explicit CVE IDs take priority;
    falls back to a keyword search when the alert type suggests exploitation
    (e.g. threat_type == "Exploit Attempt") but names no CVE directly.
    """
    explicit = extract_cve_ids(alert_text)
    if explicit:
        results = [lookup_by_id(cid) for cid in explicit]
        return [r for r in results if r]

    if "exploit" in (threat_type or "").lower():
        keyword_match = re.search(r"\b([A-Za-z][\w.-]{2,30})\s+exploit", alert_text or "", re.IGNORECASE)
        keyword = keyword_match.group(1) if keyword_match else None
        if keyword:
            return search_by_keyword(keyword)

    return []
