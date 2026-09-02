---
prompt_id: 4
category: Detection engineering
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

Create a Splunk query that could detect suspicious PowerShell activity related to MITRE ATT&CK technique T1059. Explain how the query works and what indicators it is looking for.

## Response

## The query

```spl
index=windows (sourcetype=XmlWinEventLog:Microsoft-Windows-Sysmon/Operational EventCode=1)
    OR (sourcetype=WinEventLog:Security EventCode=4688)
| eval process       = coalesce(Image, New_Process_Name),
       parent        = coalesce(ParentImage, Creator_Process_Name),
       cmdline       = coalesce(CommandLine, Process_Command_Line),
       proc_name     = lower(mvindex(split(process, "\\"), -1)),
       parent_name   = lower(mvindex(split(parent,  "\\"), -1)),
       cmd           = lower(cmdline)
| where proc_name IN ("powershell.exe", "pwsh.exe", "powershell_ise.exe")
| eval s_parent = if(parent_name IN ("winword.exe","excel.exe","powerpnt.exe",
                     "outlook.exe","msaccess.exe","visio.exe","wscript.exe",
                     "cscript.exe","mshta.exe","hh.exe","eqnedt32.exe"), 3, 0),
       s_encoded = if(match(cmd, "\s-(e|en|enc|enco|encod|encode|encoded|encodedcommand)\s"), 3, 0),
       s_download = if(match(cmd, "downloadstring|downloadfile|invoke-webrequest|\biwr\b|
                        \bcurl\b|net\.webclient|start-bitstransfer|invoke-restmethod"), 2, 0),
       s_iex = if(match(cmd, "\biex\b|invoke-expression|\.invoke\(|frombase64string"), 2, 0),
       s_hidden = if(match(cmd, "-w(indowstyle)?\s+hidden|-nop|-noprofile|-noni|-noninteractive"), 1, 0),
       s_bypass = if(match(cmd, "-ep\s+bypass|-exec(utionpolicy)?\s+(bypass|unrestricted)"), 2, 0),
       s_memory = if(match(cmd, "reflection\.assembly|virtualalloc|createthread|
                      memorystream|deflatestream|\[char\]|-join"), 2, 0),
       s_v2 = if(match(cmd, "-version\s+2|-v\s+2"), 3, 0),
       s_len = if(len(cmdline) > 1000, 1, 0)
| eval score = s_parent + s_encoded + s_download + s_iex + s_hidden
             + s_bypass + s_memory + s_v2 + s_len
| where score >= 5
| eval signals = mvfilter(mvappend(
       if(s_parent>0,"office_or_script_parent",null()),
       if(s_encoded>0,"encoded_command",null()),
       if(s_download>0,"remote_download",null()),
       if(s_iex>0,"in_memory_execution",null()),
       if(s_hidden>0,"hidden_or_noprofile",null()),
       if(s_bypass>0,"execution_policy_bypass",null()),
       if(s_memory>0,"reflective_or_obfuscated",null()),
       if(s_v2>0,"downgrade_to_v2",null()),
       if(s_len>0,"very_long_commandline",null())) != "")
| table _time host user parent_name proc_name score signals cmdline
| sort - score, - _time
```

Each `s_*` field scores one independent signal, and the alert fires on the
total rather than on any single one. A single hit is noise; three together is
an intrusion.

## How it works

**It normalises two sources first.** Sysmon Event ID 1 and Security 4688 use
different field names for the same things, so `coalesce` collapses them. That
matters practically: many environments have Sysmon on servers and only 4688 on
workstations, and a detection that silently covers half the estate is worse than
one you know is partial.

**It scores rather than matches.** This is the central design decision. Any one
of these indicators alone produces false positives — plenty of legitimate
software uses `-NoProfile`, and `-ExecutionPolicy Bypass` appears in real
deployment scripts. What almost never happens legitimately is *several at once*.
A threshold of 5 means no single signal fires the alert; `s_parent` (3) plus
`s_encoded` (3) does, and so does `-enc` with a download and hidden window.

**It explains itself.** The `signals` field lists which indicators contributed,
so the analyst sees *why* it fired before opening the command line. A detection
that produces a bare score wastes triage time.

## What each indicator means

**Office or script-host parent (weight 3).** `WINWORD.EXE` spawning PowerShell
has essentially no legitimate cause. This is the strongest single signal in the
rule and the reason the parent process is worth normalising properly rather than
matching on a full path.

**`-EncodedCommand` (3).** Base64 UTF-16LE. The regex matches the abbreviated
forms too — PowerShell accepts any unambiguous prefix, so `-e`, `-enc` and
`-encodedcommand` are all valid and attackers use the short ones precisely
because naive rules only match the long one.

**Download cmdlets (2)** and **in-memory execution (2).** `DownloadString` piped
into `IEX` is the fileless pattern: nothing touches disk for AV to scan.
`FromBase64String` catches the decode-then-run variant.

**Execution policy bypass (2).** Worth stating plainly: execution policy is not
a security boundary, it is a safety catch against accidental script execution.
Its presence is an *indicator of intent*, not evidence of a bypassed control.

**Reflective loading and obfuscation (2).** `Reflection.Assembly`,
`VirtualAlloc`, `MemoryStream` — shellcode loading. `[char]` and `-join` are
string-reassembly obfuscation, which Invoke-Obfuscation produces heavily.

**Version 2 downgrade (3).** `-version 2` is high-fidelity and underused.
PowerShell v2 predates AMSI and script block logging, so downgrading is a
deliberate evasion. There is almost no benign reason for it on a modern host.

**Very long command line (1).** Encoded payloads are long. Weak alone, useful
as a tiebreaker.

## Prerequisites, and the honest limitation

**This rule is only as good as your logging.** Windows 4688 does **not** record
command-line arguments by default — you must enable *Include command line in
process creation events*. Without it every command-line indicator scores zero
and the rule degrades to "PowerShell with an Office parent". Verify before
deploying, or you will believe you have coverage you do not.

**Obfuscation will eventually beat command-line matching.** The durable
detection for T1059.001 is **PowerShell Script Block Logging, Event ID 4104**,
which records the script *after* deobfuscation, as the engine executes it:

```spl
index=windows sourcetype="WinEventLog:Microsoft-Windows-PowerShell/Operational"
    EventCode=4104
| search ScriptBlockText="*FromBase64String*" OR ScriptBlockText="*IEX*"
    OR ScriptBlockText="*DownloadString*" OR ScriptBlockText="*Reflection.Assembly*"
| stats count values(ScriptBlockText) as script by host, user, _time
```

Run both. The command-line rule catches the launch; 4104 catches what the
launch actually did.

## Tuning before you turn it on

Run it in report mode for two weeks and baseline. The recurring false positives
will be SCCM/Intune, backup agents, monitoring tooling, and your own deployment
scripts — all of which use `-NoProfile` and `-ExecutionPolicy Bypass` freely.
Exclude them **by parent process and signing status**, not by matching on a
fragment of the command line, because command-line exclusions are trivially
copied by an attacker who has read your detection.
