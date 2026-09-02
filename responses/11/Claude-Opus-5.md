---
prompt_id: 11
category: Malware analysis
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

You are triaging a suspicious Windows executable. Outline a rapid static and dynamic analysis workflow a SOC malware analyst can complete in under 60 minutes.

## Response

## Objective

Sixty minutes is not reverse engineering. The goal is a **triage verdict** that
lets incident response act:

1. Is it malicious?
2. What family/capability class?
3. What IOCs can we hunt and block right now?
4. Does this need escalation to full RE?

Handle the sample on an isolated analysis VM, snapshotted, on a segregated
network. Rename to `.bin` and keep it in a password-protected archive when it
is not in use.

## 0–5 min · Identify and check what is already known

- **Hashes** — MD5, SHA1, SHA256.
- **VirusTotal / internal sandbox history.** If it is a known family with 55
  detections, most of the rest of this workflow is unnecessary — go straight to
  IOC extraction and scoping.
- **Where did it come from?** Email attachment, USB, web download, dropped by
  another process? Provenance shapes everything downstream.
- **First-seen date**, in your estate and globally. A sample seen only on one
  host, first seen today, is far more interesting than a widespread commodity
  binary.

**Do not upload to a public sandbox** if the sample could be targeted or contain
customer data. Uploading tips off the attacker that they have been found.

## 5–20 min · Static analysis

**File type and structure.** `file`, PEiD/DIE. Confirm it is a PE, note 32 vs
64-bit, and whether it is .NET (in which case go straight to dnSpy/ILSpy —
decompilation is often near-source and can shortcut the whole exercise).

**Packing indicators.** Section entropy above ~7.0, few imports, unusual section
names (`UPX0`, `.themida`), a `.text` section whose raw size is far smaller than
its virtual size. If packed, note it and lean harder on dynamic analysis — do
not spend triage time unpacking.

**Imports (IAT).** This is the fastest capability read:

| Imports | Suggests |
|---|---|
| `VirtualAlloc`, `WriteProcessMemory`, `CreateRemoteThread` | Process injection |
| `InternetOpenUrl`, `WinHttpSendRequest`, `socket` | Network C2 |
| `CryptEncrypt`, `CryptGenKey`, `BCrypt*` | Ransomware or config protection |
| `RegSetValueEx`, `CreateService` | Persistence |
| `IsDebuggerPresent`, `CheckRemoteDebuggerPresent` | Anti-analysis |
| `GetProcAddress` + `LoadLibrary` only | Dynamic resolution — hiding intent |

**Strings** — `strings -el` for wide chars too. Look for URLs, IPs, domains,
registry paths, mutex names, PDB paths (developer usernames leak here), command
lines, base64 blobs.

**Signature and metadata.** Signed? By whom, and is it valid? Compile timestamp
— a 2038 date or one in the future signals tampering. Version info that
impersonates a Microsoft product is a strong tell.

**Embedded resources.** Oversized or high-entropy resources often hold the real
payload.

**YARA** — run your rule set and any public ones. A family match here saves 30
minutes.

## 20–45 min · Dynamic analysis

Snapshot the VM. Start monitoring **before** detonation:

- **Procmon** — filesystem, registry, process activity
- **Process Hacker / Process Explorer** — process tree, injected memory regions
- **Wireshark** — full packet capture
- **INetSim / FakeNet-NG** — simulated internet, so the sample gets responses
  and reveals its behaviour without reaching real infrastructure
- **Regshot** — before/after registry diff

Detonate. Give it 3–5 minutes, then interact — some samples wait for mouse
movement or a reboot.

**What to record:**

- **Processes spawned**, and their command lines. Injection into `explorer.exe`
  or `svchost.exe`?
- **Files written** — especially to `%APPDATA%`, `%TEMP%`, `%PROGRAMDATA%`
- **Registry persistence** — Run keys, services, scheduled tasks
- **Mutexes** — often family-specific and excellent hunting IOCs
- **Network** — DNS queries, IPs, HTTP paths, User-Agent, JA3/JA4 fingerprint,
  certificate details. The User-Agent string alone is frequently a reliable
  family indicator.
- **Anti-analysis behaviour** — did it exit immediately? Check for VM artefact
  detection, and retry on a hardened VM if so.

**Memory dump the running process.** Packed samples unpack themselves in memory;
strings from a dump often reveal the C2 config that static analysis could not.

## 45–60 min · Verdict and output

**Write the triage note:**

- Verdict: malicious / suspicious / benign, with confidence
- Family and capability class
- ATT&CK techniques observed
- Whether it self-propagates, encrypts, or steals credentials — these change the
  IR response
- Escalate to full RE? Justify either way.

**Hand IR the actionable set:**

| Type | Use |
|---|---|
| File hashes | Block and hunt |
| C2 domains/IPs | Block, hunt retroactively 90 days |
| Mutex names | Hunt for other infected hosts |
| Persistence paths | Remediation checklist |
| Registry keys | Remediation checklist |
| YARA rule | Estate-wide sweep |

**Then hunt the estate immediately.** The most valuable output of triage is not
the report — it is the answer to *"how many other machines have this?"*, and
that query should run before the report is finished.

## Escalate to full RE when

- Targeted rather than commodity, and attribution matters
- Custom crypto or an unrecognised protocol
- Heavy anti-analysis that defeated the sandbox
- Destructive capability with unclear trigger conditions
- Legal or regulatory action will depend on the findings
