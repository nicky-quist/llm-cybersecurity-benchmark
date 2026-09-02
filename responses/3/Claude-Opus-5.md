---
prompt_id: 3
category: Incident investigation
model: Claude-Opus-5
vendor: Anthropic
api_id: claude-opus-5
max_tokens: 2000
collected_utc: 2026-09-02T00:20:00Z
collected_via: claude-code-session
collection_caveat: >
  Produced by Claude Opus 5 inside an interactive Claude Code session, not by a
  clean API call through harness/collect.py. See responses/9/Claude-Opus-5.md for
  the full caveat. Re-collect with collect.py before treating any comparison
  built on it as a clean result.
---

## Prompt

A SOC analyst sees the following sequence of events: 1. A user opens a Microsoft Word document from email. 2. Word spawns powershell.exe. 3. PowerShell runs a command with the flag -EncodedCommand. 4. Shortly after, the system connects to an external IP address. Explain what might be happening and what steps the SOC analyst should take to investigate.

## Response

## What this looks like

This is a textbook macro-based initial access chain, and each step raises the
confidence of the one before it.

**Word spawning `powershell.exe` is the anchor.** Word has no legitimate reason
to launch a shell. Nothing in normal business document use produces that
parent-child relationship. On its own that would justify investigation.

**`-EncodedCommand` removes the benign explanations.** The flag takes
base64-encoded UTF-16LE. Legitimate automation occasionally uses it to avoid
quoting problems, but legitimate automation is not being launched by Word from
an email attachment. Combined with step 2 this is close to conclusive.

**The outbound connection is the payload stage.** Most likely the encoded
command is a downloader — fetch a second stage and run it in memory, so nothing
lands on disk for file-based AV.

Mapped to ATT&CK: T1566.001 (spearphishing attachment) → T1204.002 (user
execution) → T1059.005 (VBA) → T1059.001 (PowerShell) → T1105 (ingress tool
transfer) → then whatever the second stage does.

**Treat this as a live compromise, not a suspicious alert.** By the time the
outbound connection succeeded, code the attacker chose was running as that user.

## Immediate actions — before finishing the investigation

The temptation is to investigate first. Don't. Steps 1–4 have already happened;
step 5 is the attacker's, and loaders move fast.

1. **Network-isolate the host.** EDR containment, not power-off — you need
   memory. If the tooling can only quarantine or kill, isolate is still right.
2. **Do not log the user off or reboot.** That destroys process memory,
   which holds the decoded payload, injected code, and possibly the C2 config.
3. **Block the external IP/domain** at the proxy and firewall, and check
   *tenant-wide* whether any other host reached it. That query usually decides
   whether this is one machine or twenty.
4. **Preserve the email** in its original form, headers included, and search
   the mail gateway for the same sender, subject, and attachment hash across
   all mailboxes. Quarantine matches.

## Investigation

### 1. Decode the command — this is the highest-value single step

Pull the full command line from the process-creation event (Sysmon Event ID 1,
or Windows 4688 with command-line auditing enabled — it is off by default and
its absence here is itself a finding).

```powershell
[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('<blob>'))
```

Decode it on an **isolated analysis system**, never on the affected host, and
never by executing it. If it decodes to another layer of obfuscation — gzip,
`FromBase64String` again, string reversal — keep peeling.

What you are looking for: the download URL, the destination path, any
persistence commands, and the C2 address.

### 2. Get the deobfuscated script from the logs

**PowerShell Script Block Logging, Event ID 4104**, records script content
*after* deobfuscation, as the engine sees it. If it is enabled, this is better
than your manual decode — it shows what actually ran, including any stages
fetched at runtime. Event ID 4103 (module logging) and the transcript directory
are the fallbacks.

### 3. Build the process tree

From `WINWORD.EXE` down. Note every child, and every *grandchild* — the
PowerShell may have spawned `rundll32`, `regsvr32`, `mshta`, or written and run
a binary. Sysmon Event ID 1 with parent tracking, or the EDR's process graph.

### 4. Establish what the outbound connection did

- Sysmon Event ID 3 for the connection, tied to the PID
- Proxy and firewall logs: bytes sent versus received. A large **outbound**
  volume means exfiltration, not just download.
- Was the destination reached again on a regular interval? Beaconing means an
  interactive implant, which changes the severity.
- Enrich the IP: passive DNS, VirusTotal, hosting provider, certificate.

### 5. Hunt for persistence

Assume it exists until you have checked:

- Registry Run/RunOnce keys, and `HKCU` as well as `HKLM`
- Scheduled tasks created around the event time
- New services, WMI event subscriptions
- Startup folder, and Office-specific footholds — the global template
  `Normal.dotm`, and any Office add-ins

### 6. Scope the identity, not just the host

The code ran as the user. So:

- What did that account access afterwards — file shares, mailbox, SaaS?
- Any sign of credential theft: LSASS access (Sysmon Event ID 10), `mimikatz`
  strings, suspicious `lsass` dumps?
- **Reset that user's password and revoke their sessions and tokens.** Cleaning
  the endpoint while leaving stolen credentials live is the common way these
  recur a week later.
- Does the user hold local admin, or privileged group membership?

### 7. Lateral movement

Check for outbound SMB, WinRM, RDP or WMI from this host to internal systems
after the event time, and authentication events for that user on other machines.

## What to record and decide

- **Time of initial execution** — the boundary between clean and in-scope.
- **Whether the second stage was retrieved successfully.** If the download
  failed, or the C2 was already sinkholed, impact is far lower — worth knowing
  before you declare a major incident.
- **Whether credential theft occurred.** This is the difference between
  reimaging one laptop and running a domain-wide response.

## Remediation

Reimage rather than clean — once an unknown second stage has run as the user,
you cannot enumerate what changed with confidence. Reset the user's credentials,
revoke tokens, keep the IOCs (hash, URL, IP, C2 domain) in blocklists and hunt
them retroactively across 30–90 days of logs.

Afterwards, the questions worth asking: why did the attachment reach the inbox,
why were macros enabled from an internet-sourced file, and was command-line and
script-block logging on. If it was not, turn it on — most of the investigation
above depends on it.
