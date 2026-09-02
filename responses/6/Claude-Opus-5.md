---
prompt_id: 6
category: Threat intelligence
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

Explain the difference between Indicators of Compromise (IOCs) and Tactics, Techniques, and Procedures (TTPs). Why are TTPs often considered more valuable for long-term threat detection?

## Response

## The distinction

**IOCs are artefacts.** Specific, observable values that indicate a particular
intrusion: a file hash, an IP address, a domain, a registry key, a mutex, a
certificate thumbprint, a User-Agent string. They answer *"have I seen this
exact thing?"*

**TTPs are behaviour.** How an adversary operates, at three levels of
abstraction:

- **Tactic** — the goal. *Credential Access.*
- **Technique** — the method. *T1003.001, LSASS memory dumping.*
- **Procedure** — the specific implementation. *Using `comsvcs.dll`
  `MiniDump` via rundll32 to avoid dropping Mimikatz.*

They answer *"is something behaving the way this adversary behaves?"*

## The Pyramid of Pain

David Bianco's model is the clearest framing, and it explains the value
difference directly. Each level up costs the adversary more to change:

| Level | Pain to change |
|---|---|
| Hash values | **Trivial** — recompile, flip a byte |
| IP addresses | **Easy** — new VPS, minutes |
| Domain names | **Simple** — new registration, hours |
| Network/host artefacts | **Annoying** — some rework |
| Tools | **Challenging** — rebuild or re-tool |
| **TTPs** | **Tough** — retrain the operator |

A hash changes every build. An IP changes when the VPS is rotated. But the fact
that an actor phishes with a macro, spawns PowerShell, dumps LSASS and moves
laterally over SMB is a reflection of how the *people* work — their training,
their playbooks, their tooling preferences. Changing that means changing the
operators.

## Why TTPs last longer

**IOCs expire on arrival.** Threat intel feeds routinely carry indicators that
were burned before you ingested them. An IP blocked today was likely abandoned
last week. This is not a criticism of feeds — it is intrinsic to the artefact
class.

**IOCs have no coverage against new campaigns.** A hash-based detection catches
exactly one binary. A behavioural detection for "Office spawns a shell" catches
every campaign that uses that chain, including ones that did not exist when the
rule was written.

**IOCs are trivially cheap to evade.** Polymorphic packers, domain generation
algorithms, and fast-flux hosting exist specifically to make indicator matching
useless. Fifty thousand hashes may all be the same malware family.

**TTPs survive re-tooling.** When an actor switches from Cobalt Strike to Sliver,
every tool-level indicator breaks. But if they still dump LSASS and still move
over WMI, behavioural detections keep firing.

Concretely: after Emotet's January 2021 takedown, every IOC associated with it
became worthless overnight. The *technique* — macro → PowerShell →
`-EncodedCommand` → download — kept detecting IcedID, Qakbot and BazarLoader,
because it was never about Emotet.

## Where IOCs are still the right tool

This is not an argument that IOCs are obsolete, and treating it that way is a
mistake.

- **Retrospective hunting.** A new indicator lets you search 90 days of logs and
  answer "were we hit?" — behaviour cannot do that as precisely.
- **High-confidence blocking.** IOCs are cheap to deploy, near-zero false
  positive, and require no tuning. Blocking a known C2 IP costs nothing.
- **Attribution and clustering.** Infrastructure overlap is how campaigns get
  linked to actors.
- **Speed.** During an active incident, IOCs let you scope in minutes.
- **Confirmation.** A behavioural alert plus a matching IOC is far stronger
  evidence than either alone.

The realistic split: **IOCs for scoping and blocking, TTPs for detecting.**

## The cost of TTP detection, stated honestly

TTP-based detection is more valuable *and* more expensive:

- **Higher false positive rates.** "PowerShell with an encoded command" has real
  benign instances; a hash match does not. Tuning is continuous work.
- **Better telemetry required.** Behavioural detection needs process lineage,
  command lines and script content. Hash matching needs almost nothing.
- **Analyst skill.** A behavioural alert needs someone who can judge whether the
  behaviour is malicious in context. An IOC match is self-evident.
- **Maintenance.** Behavioural rules drift as the environment changes and need
  continuous validation.

## How to use them together

ATT&CK is the shared vocabulary. Map your detections to techniques, then measure
coverage as a matrix — which techniques you can detect, and with what
confidence. That turns "we have 4,000 rules" into "we have coverage of Credential
Access but a gap in Defense Evasion", which is an answerable question.

Then: block on IOCs, alert on TTPs, hunt on both, and use each to enrich the
other. When a behavioural detection fires, the artefacts it produces become
IOCs for retrospective scoping. When an IOC hits, the behaviour around it
becomes a candidate detection.
