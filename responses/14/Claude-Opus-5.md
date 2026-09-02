---
prompt_id: 14
category: Threat hunting
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

Create a threat hunt hypothesis for living-off-the-land binaries (LOLBins) and list the telemetry, pivot fields, and success criteria.

## Response

## Hypothesis

> **An adversary with existing access is using signed Microsoft binaries
> (`certutil`, `bitsadmin`, `regsvr32`, `mshta`, `rundll32`, `msbuild`,
> `installutil`) to download, decode and execute payloads, and this activity is
> not alerting because the binaries are signed, allow-listed and present on every
> host.**

**Falsifiable prediction:** if this is happening, LOLBin invocations will exist
whose *arguments* are anomalous for the host role, whose *parent process* is
unusual, or which are followed within minutes by network egress or child-process
creation. If none of those exist across 30 days, the hypothesis is not supported
in this environment.

**Why it is worth hunting rather than detecting:** these binaries are executed
legitimately thousands of times a day. The malicious use is distinguishable only
by argument pattern and context, which is exactly the shape of problem that
suits hunting better than a standing rule.

**Scope:** all Windows endpoints and servers, 30-day lookback.

## Telemetry required

| Source | Events | Purpose |
|---|---|---|
| Sysmon | ID 1 (process + command line + parent) | Primary |
| Sysmon | ID 3 (network by PID) | Ties LOLBin to egress |
| Sysmon | ID 7 (image load) | Unmanaged PowerShell, DLL side-loading |
| Sysmon | ID 11 (file create) | Dropped payloads |
| Security | 4688 **with command line enabled** | Fallback where Sysmon is absent |
| PowerShell | 4104 | Deobfuscated script content |
| Proxy / firewall | Egress with process attribution | Download confirmation |
| DNS | Query logs | Newly-registered / rare domains |
| EDR | Process tree | Fast pivoting |

**Precondition to verify first:** command-line logging must be on. If it is not,
this hunt cannot run — and discovering that is itself a valuable finding worth
reporting.

## Pivot fields

- `ParentImage` / `InitiatingProcessFileName` — the strongest signal
- `ProcessCommandLine` — argument patterns
- `User` / `AccountName` — service accounts running LOLBins interactively
- `DeviceName` + `DeviceRole` — a workstation is not a build server
- `RemoteIP` / `RemoteUrl` / `RemoteDomain`
- `ProcessId` → child processes, network events, file writes
- `Timestamp` — clustering, and out-of-hours activity
- `FileHash` of anything written

## Hunt queries

**1. `certutil` as a downloader or decoder**

```kql
DeviceProcessEvents
| where FileName =~ "certutil.exe"
| where ProcessCommandLine has_any ("-urlcache", "-decode", "-encode",
                                    "-f http", "-split", "verifyctl")
| project Timestamp, DeviceName, AccountName, InitiatingProcessFileName,
          ProcessCommandLine
```

`certutil` is a certificate utility. Legitimate use almost never involves URLs
or base64 decoding.

**2. `regsvr32` / `mshta` with a remote scriptlet**

```kql
DeviceProcessEvents
| where FileName in~ ("regsvr32.exe", "mshta.exe")
| where ProcessCommandLine has_any ("http://", "https://", "scrobj.dll",
                                    "javascript:", "vbscript:")
```

The "Squiblydoo" pattern. Very low benign rate.

**3. Rare parent-child pairs — the highest-yield query**

```kql
DeviceProcessEvents
| where FileName in~ ("certutil.exe","bitsadmin.exe","regsvr32.exe","mshta.exe",
                      "rundll32.exe","msbuild.exe","installutil.exe","wmic.exe",
                      "cmstp.exe","forfiles.exe","pcalua.exe")
| summarize HostCount = dcount(DeviceName), Executions = count(),
            Sample = any(ProcessCommandLine)
    by FileName, InitiatingProcessFileName
| where HostCount <= 3
| order by HostCount asc
```

**Stack counting** — rank combinations by rarity rather than matching known bad.
This finds tradecraft nobody has written a signature for yet, which is the point
of hunting.

**4. LOLBin followed by egress within 5 minutes**

```kql
let lolbins = DeviceProcessEvents
    | where FileName in~ ("certutil.exe","bitsadmin.exe","mshta.exe","regsvr32.exe")
    | project ExecTime = Timestamp, DeviceName, ProcessId, ProcessCommandLine;
lolbins
| join kind=inner (
    DeviceNetworkEvents
    | where not(ipv4_is_private(RemoteIP))
    | project NetTime = Timestamp, DeviceName, InitiatingProcessId = ProcessId,
              RemoteIP, RemoteUrl)
  on DeviceName
| where NetTime between (ExecTime .. ExecTime + 5m)
```

**5. `msbuild` / `installutil` outside developer machines**

```kql
DeviceProcessEvents
| where FileName in~ ("msbuild.exe", "installutil.exe", "regasm.exe", "regsvcs.exe")
| where DeviceName !in (developer_hosts)
```

`msbuild` compiles and executes inline C# from an XML file. On a finance
workstation there is no benign explanation.

**6. Signed binary running from a non-standard path**

A `certutil.exe` in `%TEMP%` is a copied binary, not the system one — often a
rename to defeat name-based rules.

## Success criteria

**The hunt succeeded if any of these is true** — note that "found nothing" is a
legitimate and useful outcome, provided the coverage question is answered:

1. **Confirmed malicious activity found** → escalate to IR, extract IOCs.
2. **A detection gap identified.** Even with no compromise, if the hunt shows
   `certutil -urlcache` would not have alerted, that is a new rule and a real
   deliverable.
3. **A telemetry gap identified.** Hosts missing Sysmon or command-line logging —
   quantified, with a remediation ticket.
4. **A baseline produced.** Documented legitimate LOLBin use per host role, which
   makes every future hunt and rule cheaper to tune.
5. **New detections shipped.** At least two rules from queries 1–3, validated
   with Atomic Red Team.

**Explicit non-criteria:** "number of alerts generated" is not a success measure.
A hunt that produces 400 low-quality alerts is worse than one that produces none
and a tuned rule.

## Deliverables

- Findings report: what was hunted, what was found, what was ruled out
- Coverage statement: which hosts had adequate telemetry, and which did not
- New/updated detection rules with validation evidence
- Baseline document of expected LOLBin use by role
- Next-iteration hypothesis, informed by what this one ruled out
