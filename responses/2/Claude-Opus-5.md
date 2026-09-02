---
prompt_id: 2
category: SOC detection
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

From a SOC analyst perspective, what detection methods could identify malicious use of T1059 (Command and Scripting Interpreter)? Include specific Windows event logs, telemetry sources, or security monitoring techniques that could help detect this activity.

## Response

## The core problem

You cannot detect T1059 by looking for the interpreter. `powershell.exe` and
`cmd.exe` run thousands of times a day in a healthy enterprise. Detection has to
key on **context** — who launched it, what it was told to do, and what it did
next.

## Telemetry, in order of value

### 1. PowerShell Script Block Logging — Event ID 4104

The single highest-value source for T1059.001, and the one most often missing.
It records script content **after deobfuscation**, as the engine executes it. An
attacker can base64-encode, concatenate strings, insert backticks and reverse
arrays; 4104 still shows the real script, because the engine had to decode it to
run it.

Enable via GPO: *Administrative Templates → Windows Components → Windows
PowerShell → Turn on PowerShell Script Block Logging*.

Watch for: `Invoke-Expression`/`IEX`, `DownloadString`, `FromBase64String`,
`Reflection.Assembly`, `VirtualAlloc`, `Add-Type`, `Net.WebClient`,
`Invoke-Mimikatz`, `AmsiScanBuffer` (AMSI bypass attempts).

Note warning-level 4104 events fire on suspicious content even without full
logging enabled — worth querying even in under-instrumented estates.

### 2. Process creation with command line

**Sysmon Event ID 1** (preferred) or **Security Event ID 4688**.

Critically: **4688 does not log command-line arguments by default.** Enable
*Include command line in process creation events*. Without it, the majority of
the detections below score nothing, and you will believe you have coverage you
do not have.

Sysmon Event ID 1 also gives you hashes, the signing status, and — most
usefully — `ParentImage`.

### 3. Module logging — Event ID 4103

Records pipeline execution details. Noisier than 4104 and largely superseded by
it, but useful for reconstructing exactly what a script touched.

### 4. Supporting sources

- **Sysmon Event ID 3** — network connections tied to a PID. Ties "PowerShell
  ran" to "PowerShell called out".
- **Sysmon Event ID 7** — image loads. Catches `System.Management.Automation.dll`
  loading in a process that is *not* `powershell.exe`, which is how unmanaged
  PowerShell hosts evade the logging above entirely.
- **Sysmon Event ID 11** — file creation, for dropped second stages.
- **Sysmon Event ID 10** — process access, for LSASS credential theft.
- **Windows Security 4104/4105/4106** — remoting.
- **EDR process trees** — the fastest way to see the whole chain.
- **AMSI** — lets AV inspect in-memory script content at execution time.

## Detections worth building

**Parent-child anomalies.** The strongest single signal. Alert when a shell's
parent is:

- `winword.exe`, `excel.exe`, `powerpnt.exe`, `outlook.exe` — macro execution
- `wscript.exe`, `cscript.exe`, `mshta.exe` — script-host chains
- `w3wp.exe`, `httpd.exe`, `tomcat.exe` — **webshell**, and worth its own
  high-severity rule
- `services.exe` in unexpected contexts

**Encoded and obfuscated command lines.** Match `-e`, `-en`, `-enc` through
`-encodedcommand` — PowerShell accepts any unambiguous prefix and attackers use
the short forms because naive rules only match the long one. Also
`-w hidden`, `-nop`, `-ep bypass`.

**PowerShell v2 downgrade.** `-version 2` is high-fidelity. v2 predates AMSI and
script block logging, so it is a deliberate evasion with essentially no benign
use on a modern host. Remove the v2 feature entirely if you can.

**Fileless download-and-execute.** `DownloadString` or `Invoke-WebRequest`
combined with `IEX` in one command line.

**Encoded-command entropy.** Rather than matching known-bad strings, score the
Shannon entropy of the command line. Obfuscated payloads are high-entropy; the
approach survives obfuscation changes that string matching does not.

**Unmanaged PowerShell hosts.** `System.Management.Automation.dll` loading into
a process that is not a known PowerShell host. This is how tools bypass 4104
altogether — the detection has to come from image loads, not from PowerShell's
own logging.

**Rare-command analytics.** Stack-count command lines across the estate over 30
days; alert on ones seen on one or two hosts. This finds novel tradecraft that
signature rules miss.

## Hunting ideas

- Long-tail analysis of PowerShell parents, ranked by rarity
- Hosts where PowerShell ran for the first time ever
- PowerShell making outbound connections to newly-registered domains
- Script block content containing base64 blobs over 500 characters
- Scheduled tasks whose action is a shell command, created in the last 7 days

## Hardening that makes detection easier

- **Constrained Language Mode** blocks the .NET reflection most offensive
  tooling needs, without removing PowerShell.
- **Remove PowerShell v2.**
- **JEA** for administrative use.
- **Block Office child processes** via ASR rule
  `D4F940AB-401B-4EFC-AADC-AD5F3C50688A`. Deploy in audit mode first — it will
  break something, and you want to know what before it breaks in production.
- **Signed-script enforcement** where the environment allows it.

## The honest caveat

Everything above depends on logging being on and forwarded. The most common
failure in real SOCs is not a bad rule; it is a good rule running against 4688
events with no command line in them. Verify ingestion per-host before trusting
coverage numbers.
