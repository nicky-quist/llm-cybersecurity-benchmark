---
prompt_id: 15
category: Digital forensics
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

A compromised endpoint may have credential theft activity. Provide a prioritized forensic collection plan that preserves evidence integrity.

## Response

## The governing principle

Collect in **order of volatility** — most volatile first. RFC 3227 is the
standard reference, and for a credential-theft case it is not academic: the
credentials themselves live in memory. Every minute the host stays running
degrades that evidence; every reboot destroys it entirely.

**Do not reboot. Do not shut down. Do not log off.**

## Before touching anything

1. **Isolate at the network level**, not by powering off. EDR network
   containment, or a switch port ACL. This stops exfiltration and lateral
   movement while preserving RAM.
2. **Photograph the screen** if anything is displayed — dialogs, open tools, a
   ransom note.
3. **Start the chain of custody form now.** Every action, who did it, when, with
   what tool and version. If this ends up in litigation or an insurance claim,
   the log is the evidence that the evidence is sound.
4. **Note system time and drift** against a known source. Every timeline you
   build depends on it.

## Priority 1 — Memory (0–15 min)

**This is the whole case.** LSASS holds NTLM hashes, Kerberos tickets and
sometimes cleartext credentials. Mimikatz artefacts, injected code and C2
configuration exist only here.

- **Full physical memory dump** — WinPmem, Magnet RAM Capture, FTK Imager,
  Belkasoft. Write to external media or a network share, never to the local
  disk (that overwrites unallocated space holding deleted artefacts).
- Hash the image immediately (SHA256) and record it.
- **Pagefile.sys / swapfile.sys / hiberfil.sys** — memory that has already been
  paged out. Frequently overlooked and frequently decisive.

Run the acquisition tool from external media, and accept that it perturbs the
system slightly. Document that; a small, documented footprint is far better than
lost evidence.

## Priority 2 — Volatile system state (15–30 min)

Capture to external media, with output hashed:

- Running processes with full paths, PIDs, parents, command lines
- Network connections and listening ports (`netstat -anob`)
- Loaded DLLs, especially anything unsigned or in a user-writable path
- Logged-on users and active sessions (`query user`, `qwinsta`)
- Open handles and named pipes — Mimikatz and PsExec leave distinctive ones
- Scheduled tasks, services, autorun entries
- ARP and DNS caches
- Clipboard contents

## Priority 3 — Credential-specific artefacts (30–60 min)

Targeted, because these directly evidence theft:

- **LSASS access events** — Sysmon Event ID 10. *Which process opened LSASS,
  with what access mask?* `0x1010` and `0x1410` are the classic dumping masks.
  This is the single most probative log entry in a credential-theft case.
- **Security event log** — 4624 (logon, note the type), 4625, 4648 (explicit
  credentials), 4672 (special privileges), 4768/4769 (Kerberos TGT/TGS —
  Kerberoasting shows here), 4776 (NTLM)
- **Sysmon** — 1, 3, 7, 8 (CreateRemoteThread), 10, 11
- **Registry hives** — SAM, SYSTEM, SECURITY, and the user's NTUSER.DAT
- **DPAPI master keys** and the Credential Manager vault
- **Browser credential stores**
- **`%TEMP%`, `%APPDATA%`** — dropped dump files; look for `lsass.dmp` or any
  large file created around the incident window
- **Prefetch** — evidence of execution, including for deleted binaries
- **Shimcache / Amcache** — execution history that survives deletion
- **`.bash_history`-equivalents** — PowerShell `ConsoleHost_history.txt`

## Priority 4 — Disk image (60+ min)

Full forensic image with a **write blocker** for physical media, or a live E01
acquisition if the host cannot be taken down.

- E01 format for compression and embedded hashing
- Verify the acquisition hash against the source
- If time-constrained, a **triage collection** (KAPE targets) captures the
  high-value artefacts in minutes rather than hours — a defensible middle
  ground when full imaging is impractical

## Priority 5 — Off-host evidence

Often more complete than the endpoint, and not subject to attacker tampering:

- Domain controller logs — authentication for the affected accounts
- Proxy, firewall, VPN, DNS logs
- EDR telemetry already shipped to the cloud
- Email gateway, if phishing was the entry vector
- NetFlow

## Evidence integrity throughout

- **Hash everything** at collection, and verify after transfer. Record the
  algorithm and value in the custody log.
- **Work on copies.** The original image is never analysed directly.
- **Chain of custody** unbroken: who, what, when, where, why, transfer signatures.
- **Tool validation** — record tool names and versions; use known-good, verified
  binaries from your own media, not tools found on the host.
- **Contemporaneous notes**, timestamped. Written during, not reconstructed after.
- **Secure storage**, access-controlled and logged.

## Parallel containment — do not wait for forensics

Credential theft has a blast radius beyond the endpoint. While collection runs:

- **Reset passwords** for every account that authenticated to the host, and
  **revoke Kerberos tickets and OAuth/refresh tokens** — a password reset alone
  does not invalidate a live ticket
- Consider a **`krbtgt` double-reset** if a Golden Ticket is plausible
- Check for new/modified accounts, group membership changes, new service
  principals
- Hunt the estate for the same LSASS-access pattern

## The judgement call worth stating

If the choice is between a perfect forensic process and stopping active domain
compromise, **stop the compromise.** Document the decision and its rationale.
An immaculate evidence chain for an incident that spread to the whole estate
while you preserved it is not a good outcome, and a defensible incident log
records the trade-off deliberately rather than pretending it did not exist.
