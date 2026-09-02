---
prompt_id: 19
category: Incident communications
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

Draft an executive-ready incident update structure for the first 24 hours of a ransomware investigation.

## Response

## What executives actually need

Not the investigation. They need four things: **how bad, what is broken, what
are we doing, what do you need from me.** Everything else is detail that belongs
in the technical log.

Three rules that make these updates work:

- **Lead with business impact, not technical findings.** "Order processing is
  down" lands; "we observed Cobalt Strike beaconing" does not.
- **Label confidence explicitly.** Executives will act on what you write.
  Distinguish *confirmed* from *assessed* from *unknown* — and keep the unknowns
  visible rather than letting silence imply safety.
- **Never speculate on attribution, ransom payment, or total cost** in the first
  24 hours. You will be wrong, and the wrong number becomes the anchor for every
  subsequent conversation.

## Cadence

| Time | Update | Audience |
|---|---|---|
| T+1h | Initial notification | CISO, CIO, Legal, Comms |
| T+4h | First structured update | Exec team |
| T+8h, T+12h | Situation reports | Exec team |
| T+24h | Day-one summary | Exec + Board notification if material |

Fixed times, published in advance. If there is nothing new, send "no material
change" — silence gets filled with speculation, and an executive chasing you for
an update is an executive not doing their own job.

## The template

---

### RANSOMWARE INCIDENT — SITUATION REPORT #[n]

**Incident:** INC-[number] · **Severity:** [Critical/High] ·
**Time:** [timestamp + timezone] · **Next update:** [time]
**Prepared by:** [name, role] · **Distribution:** [list] ·
**Classification:** [Confidential — Legal Privilege if applicable]

---

**1. BOTTOM LINE (3 sentences maximum)**

> Ransomware was deployed across [N] servers in [environment] beginning
> approximately [time]. [Business function] is unavailable; [function] continues
> to operate normally. Containment is in place and we are working to restore
> [priority system] with an estimated timeline of [X] hours.

**2. BUSINESS IMPACT**

| Function | Status | Workaround | Est. restoration |
|---|---|---|---|
| Order processing | Down | Manual entry | 12h (assessed) |
| Email | Operational | — | — |
| Customer portal | Degraded | Read-only | 6h (assessed) |

- **Customers affected:** [number, or "assessment in progress"]
- **Revenue impact:** [quantified per hour if known, else "being quantified"]
- **Regulatory obligations triggered:** [GDPR 72h / SEC 8-K / HIPAA / none
  identified yet] — with a clock, if one is running

**3. WHAT WE KNOW — with confidence levels**

- **CONFIRMED:** Ransomware executed on [N] hosts. Encryption began [time].
- **CONFIRMED:** Initial access via [vector] at [time], [X] days before
  encryption.
- **ASSESSED (moderate confidence):** [N] systems affected in total; scoping
  continues.
- **UNKNOWN:** Whether data was exfiltrated prior to encryption. *This is the
  single most consequential open question and drives our regulatory and
  notification obligations.*
- **UNKNOWN:** Full extent of lateral movement.

**4. WHAT WE ARE DOING**

*Completed:*
- Isolated affected network segments at [time]
- Disabled [N] compromised accounts; reset privileged credentials
- Engaged [IR firm] under legal privilege

*In progress:*
- Forensic imaging of patient-zero host — ETA [time]
- Backup integrity verification — **critical path for recovery**
- Exfiltration assessment via egress log review

*Next 12 hours:*
- Restore [priority system] from [date] backup
- Complete estate-wide sweep for persistence

**5. DECISIONS NEEDED FROM LEADERSHIP**

The section executives read first. Be specific and give a deadline.

- **[DECISION]** Authorise emergency spend of £[X] for IR retainer expansion —
  needed by [time]
- **[DECISION]** Approve customer notification approach — Legal recommends
  [option] — needed by [time]
- **[AWARENESS]** Recovery from backup means losing up to [N] hours of
  transactions

**6. RISKS AND DEPENDENCIES**

- Backups from [date] onward may be compromised; verification in progress
- If exfiltration is confirmed, regulatory notification clock started at [time]
- [Third party] dependency for [system] restoration

**7. COMMUNICATIONS STATUS**

- Internal: [held / issued at time]
- Customers: [not yet / issued]
- Regulators: [assessment in progress / notified at time]
- Media: [no enquiries / holding statement prepared]
- Law enforcement: [reported / not yet]

---

## Practical notes

**Route it through Legal.** Mark communications as privileged where your counsel
advises. Incident documents get discovered in litigation, and how they were
written matters.

**Write for the person who joins at update #4.** Each report should stand alone.
Executives will not read the back catalogue.

**Do not put ransom decisions in a written update** without Legal and Comms
present. That is a conversation, not a document.

**Keep "unknown" prominent.** The instinct under pressure is to project control
by minimising uncertainty. Resist it — an executive who discovers at T+48h that
exfiltration was always possible, but was never flagged, will not trust the next
report.

**Separate the technical log from the executive update.** Detailed IOCs,
timelines and forensic findings go in a parallel technical record. Mixing them
buries the decisions in detail nobody in the room can act on.
