---
prompt_id: 13
category: SIEM engineering
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

Design a SIEM correlation rule that links suspicious process execution, outbound network traffic, and privilege escalation attempts on the same host within 30 minutes.

## Response

## Design intent

Any one of these three signals is noisy enough to be unusable on its own.
Together, on the same host, inside 30 minutes, they describe an intrusion in
progress: **execute → call home → escalate.** The rule's job is to require the
combination and to make the resulting alert self-explanatory.

## The rule (Sentinel KQL)

```kql
let window = 30m;
let lookback = 1d;

let suspicious_exec =
    DeviceProcessEvents
    | where Timestamp > ago(lookback)
    | where (InitiatingProcessFileName in~ ("winword.exe","excel.exe","powerpnt.exe",
                                            "outlook.exe","mshta.exe","wscript.exe",
                                            "cscript.exe","w3wp.exe"))
         or (FileName in~ ("powershell.exe","cmd.exe","wscript.exe","rundll32.exe",
                           "regsvr32.exe","mshta.exe","certutil.exe","bitsadmin.exe")
             and ProcessCommandLine matches regex @"(?i)\s-(enc|e|nop|w\s+hidden|ep\s+bypass)|downloadstring|frombase64string|iex\b")
    | project ExecTime = Timestamp, DeviceName, DeviceId,
              ExecAccount = AccountName, ExecProcess = FileName,
              ExecParent = InitiatingProcessFileName, ExecCmd = ProcessCommandLine,
              ExecPid = ProcessId;

let outbound =
    DeviceNetworkEvents
    | where Timestamp > ago(lookback)
    | where ActionType == "ConnectionSuccess"
    | where not(ipv4_is_private(RemoteIP))
    | where RemotePort !in (80, 443) or isnotempty(RemoteUrl)
    | project NetTime = Timestamp, DeviceName, RemoteIP, RemotePort, RemoteUrl,
              NetProcess = InitiatingProcessFileName;

let privesc =
    union
      (DeviceEvents
       | where Timestamp > ago(lookback)
       | where ActionType in ("NamedPipeEvent","ProcessPrimaryTokenModified",
                              "SecurityGroupMemberAdded")),
      (SecurityEvent
       | where TimeGenerated > ago(lookback)
       | where EventID in (4672, 4728, 4732, 4756, 4697, 4720)
       | extend Timestamp = TimeGenerated, DeviceName = Computer,
                ActionType = strcat("EventID_", EventID))
    | project EscTime = Timestamp, DeviceName, EscAction = ActionType,
              EscAccount = tostring(column_ifexists("AccountName", ""));

suspicious_exec
| join kind=inner outbound on DeviceName
| where NetTime between (ExecTime .. ExecTime + window)
| join kind=inner privesc on DeviceName
| where EscTime between (ExecTime .. ExecTime + window)
| summarize
    FirstSeen        = min(ExecTime),
    LastSeen         = max(EscTime),
    Processes        = make_set(ExecProcess, 8),
    ParentProcesses  = make_set(ExecParent, 8),
    CommandLines     = make_set(ExecCmd, 5),
    RemoteIPs        = make_set(RemoteIP, 10),
    RemoteUrls       = make_set(RemoteUrl, 10),
    EscalationEvents = make_set(EscAction, 8),
    Accounts         = make_set(ExecAccount, 5)
    by DeviceName
| extend SpanMinutes = datetime_diff('minute', LastSeen, FirstSeen)
| extend Severity = case(
      array_length(EscalationEvents) >= 2 and array_length(RemoteIPs) >= 2, "Critical",
      array_length(EscalationEvents) >= 2, "High",
      "Medium")
| order by FirstSeen desc
```

## How it works

**Three independent stages, joined on host and time.** Each stage is defined as
its own `let` block so it can be tested in isolation — a correlation rule you
cannot debug stage-by-stage is a rule you will disable within a month.

**The window is anchored to execution**, not floating. `NetTime` and `EscTime`
must both fall in `[ExecTime, ExecTime + 30m]`. This enforces the *causal
ordering* that matters: execution first, then the other two. A privilege
escalation that happened an hour *before* an unrelated PowerShell run is not
this rule's business.

**Escalation is drawn from two sources** because neither is complete alone.
Defender's `DeviceEvents` carries token manipulation and named-pipe
impersonation — the artefacts of `getsystem`-style escalation. The classic
Security log carries the account-level events: 4672 (special privileges
assigned), 4728/4732/4756 (added to a privileged group), 4697 (service
installed), 4720 (account created).

**Non-standard ports OR a resolved URL.** Filtering out 80/443 entirely would
miss most real C2, which hides in HTTPS. Keeping connections that have a
`RemoteUrl` preserves web traffic while dropping raw unattributed noise.

**Severity is derived from breadth**, not from a static label. Two escalation
events plus two remote IPs is a materially worse picture than one of each, and
the analyst should see that in the queue ordering.

**The output is a populated case.** Command lines, parents, IPs, URLs, accounts
and the elapsed span — enough to make a triage decision without pivoting to
three other consoles.

## False positives, and how to cut them

The predictable sources, in order of volume:

| Source | Why it fires | Control |
|---|---|---|
| SCCM / Intune | PowerShell with bypass flags, then network, then service install | Exclude by initiating process **and** signing status |
| Vulnerability scanners | Authenticated scans generate 4672 at volume | Exclude scanner service accounts by SID |
| Backup agents | Elevated tokens, outbound traffic | Exclude by signed publisher |
| Patch windows | Everything at once | Suppress on schedule, do not exclude permanently |
| Admin workstations | Legitimately do all three | Separate, higher threshold |

**Exclude on identity and signature, not on command-line fragments.** A
command-line exclusion is a published bypass for anyone who reads your
detection.

## Before deploying

- **Run in report mode for two weeks.** Count hits per day and per host. If it
  fires more than ~5 times a day, the rule is not ready.
- **Validate with Atomic Red Team** — T1059.001, T1055, T1134 — and confirm it
  actually fires. An untested correlation rule is a assumption, not a control.
- **Check the join cost.** Three-way joins over a day of process events are
  expensive; materialise the stages or narrow the lookback if the query times
  out.
- **Verify the telemetry exists on every host in scope.** Missing command-line
  logging silently reduces this to a two-stage rule.
- **Version-control it** and re-run the validation on a schedule, so drift shows
  up as a failing test rather than as a quiet gap.
