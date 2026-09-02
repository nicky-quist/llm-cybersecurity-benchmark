---
prompt_id: 18
category: Detection validation
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

How should a SOC team validate and continuously test detection rules to reduce drift and maintain coverage over time?

## Response

## The problem

Detection rules are written once and then quietly stop working. The causes are
mundane and none of them announce themselves:

- A log source stops forwarding after an agent upgrade
- A vendor renames a field, so the rule matches nothing
- An exclusion added during tuning is broader than intended
- The attack technique evolves past the rule's assumptions
- The asset it protected was decommissioned

**A rule that fires zero times looks identical whether it is working perfectly
or completely broken.** That ambiguity is the whole problem, and the entire
programme below exists to resolve it.

## Detection-as-code

Treat detections like software, because they are:

- **Version control.** Rules in Git, changes via pull request, peer review
  before merge. Every change attributable.
- **Structured metadata** on every rule: ATT&CK technique, data source, author,
  severity, expected FP rate, last validated date, owner.
- **Sigma** as the portable source format where practical, compiled to the
  backend query language. Portability matters when you change SIEM.
- **CI pipeline** — syntax validation, schema checks, and unit tests on merge.

The metadata is what makes everything downstream measurable. Without ATT&CK
mapping you cannot compute coverage; without an owner, nothing gets fixed.

## The four layers of validation

### 1. Unit tests — does the logic work?

Every rule gets a known-good and known-bad test event. Run on every commit.
Fast, cheap, and catches the majority of syntax and logic regressions before
they ship.

### 2. Atomic testing — does it fire on real technique execution?

**Atomic Red Team** provides small, technique-scoped tests mapped to ATT&CK.

```
Invoke-AtomicTest T1059.001 -TestNumbers 1,2,3
```

Run on a schedule against a test host, then assert the corresponding alert
appeared within an expected window. This is the highest value-per-effort
activity in the whole programme.

**Automate the assertion, not just the execution.** Running the atomic and
eyeballing the console is not validation — the pipeline must check that the
alert fired and fail loudly if it did not.

### 3. Adversary emulation — does the chain work?

Atomics test techniques in isolation; real intrusions are sequences. Use
**CALDERA**, **Atomic Red Team chains**, or scripted emulation of a specific
actor's known TTPs to test whether the *correlation* rules and the analyst
workflow hold up end to end.

Cadence: quarterly, or after significant infrastructure change.

### 4. Purple team — does the human process work?

Red team executes, blue team responds, both in the room. This tests what
automation cannot: whether the alert was *triaged correctly*, whether the
analyst had the context they needed, whether the escalation path worked.

Cadence: semi-annually. Findings become new detections and playbook changes.

## Continuous health monitoring

Automated testing catches broken logic. These catch broken *plumbing*:

**Log source heartbeat.** Alert when a source stops reporting. This is the
single highest-value monitor in the programme — a missing log source silently
disables every rule that depends on it.

```kql
DeviceProcessEvents
| summarize LastSeen = max(Timestamp) by DeviceName
| where LastSeen < ago(24h)
```

**Rule silence monitoring.** Any rule that has not fired in 90 days gets
reviewed. Either it is broken, or it is unnecessary — both need a decision.

**Volume anomaly detection.** A rule whose firing rate drops 80% week-on-week is
broken until proven otherwise.

**Schema validation.** Assert the fields your rules reference still exist and
still hold the expected data types. Vendor field renames are a common and
entirely silent killer.

**Coverage mapping.** Maintain an ATT&CK Navigator layer of what you can detect
and at what confidence. Review quarterly against current threat intel — coverage
should be prioritised by what actually targets your sector, not by filling in
the matrix.

## Metrics that mean something

| Metric | What it tells you |
|---|---|
| True positive rate per rule | Is it finding real things |
| False positive rate per rule | Is it costing more than it returns |
| **Mean time to detect** | The outcome that matters |
| % rules validated in last 90 days | Programme health |
| % rules with a validation test | Test coverage of the coverage |
| Detection coverage by ATT&CK tactic | Where the gaps are |
| Alert-to-incident ratio | Signal quality |

**Deliberately not a metric: alert count.** Optimising it drives exactly the
wrong behaviour.

## Rule lifecycle

Every rule should have a documented state: **draft → testing → production →
deprecated**, with an owner and a review date. Rules that fail validation twice
in a row get pulled to testing rather than left broken in production.

**Retire rules.** A SIEM with 4,000 rules of which 600 work is worse than one
with 400 that all work, because nobody trusts the output of the first.

## Where to start

If a team has none of this today, the order that yields most first:

1. **Log source heartbeat monitoring** — cheapest, catches the most damaging
   failure class
2. **Rule silence report** — free, immediately reveals what is already broken
3. **Atomic Red Team on the top 10 rules** — proves the concept and usually
   finds one or two rules that never worked
4. **Version control + review** — stops the bleeding
5. **CI with automated assertions** — makes it durable

Steps 1 and 2 can be done in an afternoon and typically surface broken coverage
that has been invisible for months. That finding is usually what funds the rest
of the programme.
