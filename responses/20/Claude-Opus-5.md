---
prompt_id: 20
category: Security automation
model: Claude-Opus-5
vendor: Anthropic
api_id: claude-opus-5
max_tokens: 2000
collected_utc: 2026-09-02T00:40:00Z
collected_via: claude-code-session
collection_caveat: >
  Produced by Claude Opus 5 inside an interactive Claude Code session, not by a
  clean API call through harness/collect.py. See responses/9/Claude-Opus-5.md for
  the full caveat.
---

## Prompt

Propose a SOAR playbook for phishing triage that includes enrichment, decision points, analyst handoff, and post-incident learning.

## Response

## Design principle

Automate **gathering**, not **judgement**. Enrichment, containment of clearly
malicious mail, and bulk cleanup are safe to automate. Deciding that an
ambiguous message is benign is not — a false "benign" auto-close is a phish that
reached every mailbox with the SOC's blessing.

**Trigger:** user report button, mail gateway detection, or abuse@ mailbox.

## Stage 1 — Intake and normalisation (automated, <1 min)

- Ingest the `.eml` with full headers; parse into a case
- Extract: sender (envelope **and** display), reply-to, return-path,
  subject, all URLs, all attachments with hashes, embedded IPs
- **Deduplicate** against open cases by subject + sender + URL hash. Ten reports
  of one campaign is one incident, not ten tickets — this alone typically halves
  case volume.
- Auto-acknowledge to the reporting user. Cheap, and it is why people keep
  reporting.

## Stage 2 — Enrichment (automated, parallel, 2–5 min)

**Sender and authentication**
- SPF, DKIM, DMARC results from headers
- Domain age (newly registered is a strong signal), registrar, WHOIS
- Is the sender domain a **lookalike** of ours or a known partner? Levenshtein
  distance against a watchlist catches most BEC setups.
- Has this sender ever mailed us before? First-contact is significant.
- Full `Received:` chain — originating IP, geolocation, reputation

**URLs**
- Reputation: VirusTotal, URLScan, Cisco Talos, internal history
- **Detonate in a sandbox**, following redirects
- Screenshot the landing page — an analyst identifies a credential harvester
  faster from an image than from any indicator
- Does the page host a login form impersonating our SSO? High severity.

**Attachments**
- Hash lookup first — known-bad ends triage immediately
- Static analysis: macros, embedded objects, OLE streams
- Sandbox detonation for anything unknown

**Internal exposure — the query that decides severity**
- How many mailboxes received it? Search the estate, not just the reported copy.
- **Did anyone click?** Proxy and DNS logs for the URL.
- **Did anyone authenticate** after clicking? Sign-in logs for those users.
- Did anyone open the attachment? EDR file execution.
- Did anyone reply?

**Recipient context**
- Role and privilege level of recipients — an executive or finance staffer
  changes the severity

## Stage 3 — Decision points

| Condition | Action | Automation |
|---|---|---|
| Known-bad hash/URL, no clicks | Purge, block, close | **Full auto** |
| Known-bad, **clicks detected** | Purge + block + isolate + escalate | Auto-contain, **human escalation** |
| Bulk marketing / newsletter | Close, feedback to user | **Full auto** |
| Internal sender (account compromise) | Escalate immediately | **Human** |
| Credential harvester, no clicks | Purge + block, notify recipients | Auto with **notification** |
| Ambiguous | Queue for analyst | **Human** |
| BEC / wire fraud (no payload) | Escalate to Finance + Legal | **Human** |

**Two rules that keep this safe:**

1. **Never auto-close as benign.** Auto-close only on high-confidence *malicious*
   or clearly *bulk* verdicts. Ambiguity goes to a human. The asymmetry is
   deliberate — a wrongly-queued newsletter costs two minutes, a wrongly-closed
   phish costs an incident.
2. **Rate-limit destructive actions.** Cap automated purges per hour. A
   misconfigured rule that mass-deletes legitimate mail is a self-inflicted
   outage, and it has happened to real teams.

## Stage 4 — Containment (automated where safe)

- **Purge** from all mailboxes (Microsoft 365 `Search-Mailbox -DeleteContent`
  or Purview compliance search)
- **Block** sender, domain, URL at gateway and proxy
- Add IOCs to threat intel platform
- **If clicks detected:** force password reset, revoke sessions and refresh
  tokens, raise user risk in Entra ID Protection
- **If credentials entered:** treat as account compromise — full IR path
- **If attachment executed:** isolate the endpoint via EDR

## Stage 5 — Analyst handoff

The handoff is where most playbooks fail: they dump raw enrichment into a ticket
and call it triage. The case presented to the analyst should contain:

- **One-line summary and recommended verdict**, with the reasoning
- **Screenshot** of the landing page
- **Exposure numbers** — recipients, clicks, credential submissions
- **What automation already did**, explicitly, so nothing is repeated
- **The specific open question** the analyst is being asked to resolve
- **One-click actions**: purge, block, escalate, close-benign

Target: the analyst makes a decision in under 3 minutes because everything
needed is already on the screen.

## Stage 6 — Post-incident learning

The stage that is always specified and rarely built:

**Feed the reporter.** Tell the user what it was and thank them. Reporting rates
collapse without this, and user reports are the highest-value detection source
in most organisations.

**Update detections.** New IOCs to blocklists. If the campaign evaded the
gateway, raise it with the mail security vendor and write a compensating
detection.

**Retro-hunt.** Search 90 days for the same sender infrastructure, URL patterns
and hashes. Campaigns rarely start on the day you noticed them.

**Track metrics that matter:**
- Time from delivery to purge (the number that reflects real risk)
- % auto-resolved without human touch
- Click rate before purge
- **False-negative rate** — phishing that got through and was reported by users
  rather than caught by the gateway
- Reporting rate by department

**Feed awareness training.** Departments with high click rates get targeted
training. Real campaign examples are far more effective than generic material.

**Review the playbook quarterly.** Which decision branches fire most? Which
auto-verdicts did analysts overturn? An overturn rate above ~5% on any branch
means that branch's logic is wrong and should go back to human review until
fixed.
