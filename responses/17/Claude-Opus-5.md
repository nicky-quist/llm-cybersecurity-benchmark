---
prompt_id: 17
category: Identity security
model: Claude-Opus-5
vendor: Anthropic
api_id: claude-opus-5
max_tokens: 2000
collected_utc: 2026-09-01T22:45:00Z
collected_via: claude-code-session
collection_caveat: >
  Produced by Claude Opus 5 inside an interactive Claude Code session, not by a
  clean API call through harness/collect.py. See responses/9/Claude-Opus-5.md for
  the full caveat. Re-collect with collect.py before treating any comparison
  built on it as a clean result.
---

## Prompt

A company suspects password spraying against Microsoft Entra ID. Describe detection logic, triage steps, and hardening actions.

## Response

## What separates spraying from brute force

Brute force is many passwords against one account. **Spraying is one password
against many accounts**, paced under the lockout threshold. That inverts the
detection: a per-account failure counter will never fire. You have to pivot on the
*password attempt* — meaning distinct accounts targeted per source, per time
window.

## Detection logic

The signal lives in `SigninLogs`. The error codes that matter:

| Code | Meaning | Why it matters |
|---|---|---|
| 50126 | Invalid username or password | the core spray signal |
| 50053 | Account locked / IP smart-locked | you're already in it |
| 50055 | Password expired | **valid password** — the spray hit |
| 50056 | No password in store | |
| 50057 | Account disabled | **valid password** on a disabled account |
| 50076 / 50074 | MFA required | **valid password**, MFA held the line |
| 50158 | External security challenge unsatisfied | conditional access held |

The critical distinction: **50126 means the password was wrong. 50055, 50057,
50076 and 50074 mean the password was RIGHT** and something else stopped the
sign-in. A spray run that produces mostly 50126 with a handful of 50076 has
succeeded at credential discovery, and those accounts are compromised pending MFA
holding. Triage those first, always.

### Core KQL

```kql
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType in ("50126","50053","50055","50056","50057","50076","50074")
| summarize
    FailedAccounts   = dcount(UserPrincipalName),
    Attempts         = count(),
    ValidPassword    = dcountif(UserPrincipalName, ResultType in ("50055","50057","50076","50074")),
    Apps             = make_set(AppDisplayName, 10),
    Codes            = make_set(ResultType, 10)
    by IPAddress, Country = tostring(LocationDetails.countryOrRegion)
| where FailedAccounts >= 15 and Attempts / FailedAccounts <= 3
| order by FailedAccounts desc
```

The `Attempts / FailedAccounts <= 3` ratio is what makes this a *spray* detector
rather than a noisy-IP detector. Spraying is wide and shallow: many accounts, few
attempts each. A misconfigured mail client hammering one account fails that ratio.

### Detections worth adding alongside it

**1. Distributed spray.** Mature actors rotate through residential proxies, so
per-IP thresholds miss it entirely. Pivot on the *ASN* or on the whole tenant:

```kql
SigninLogs
| where TimeGenerated > ago(1h) and ResultType == "50126"
| summarize Accounts = dcount(UserPrincipalName), IPs = dcount(IPAddress)
    by bin(TimeGenerated, 10m), AutonomousSystemNumber
| where Accounts >= 25
```

**2. Legacy authentication.** Basic auth (`ClientAppUsed` in "Other clients",
IMAP4, POP3, SMTP, Exchange ActiveSync) bypasses conditional access and MFA
entirely. It is the single most common spray vector and should be alerted on
regardless of volume. Check `AADNonInteractiveUserSignInLogs` too — spray traffic
frequently lands there and analysts forget the table exists.

**3. Success after failure.** The highest-severity rule: an IP with ≥10 failures
that then produces `ResultType == 0`.

**4. Built-in signals.** Entra ID Protection's *Password spray* risk detection and
*Anomalous token* / *Unfamiliar sign-in properties*, plus Defender for Identity if
you have on-prem AD FS or Connect. Use these to corroborate, not to replace your
own rules — licensing tiers change what fires.

## Triage

1. **Separate discovered credentials from noise.** Split the account list by
   result code. The 50055/50057/50076/50074 set is your compromised-credential
   list. Everything else is background.
2. **Check for successes.** Any `ResultType == 0` from the same IPs/ASN in the
   window. If yes, this is an intrusion, not an attempted one.
3. **Look past the sign-in.** For any success, check `AuditLogs` and
   `CloudAppEvents` for: new MFA method registered, mailbox forwarding or inbox
   rules created, OAuth app consent granted, device joined, password changed. New
   MFA registration is the classic post-spray persistence step and it is often the
   only durable artefact.
4. **Characterise the source.** ASN, hosting provider, Tor/VPN, geography vs. your
   footprint. `AADNonInteractiveUserSignInLogs` for the same IP will often show
   far more volume than the interactive table.
5. **Reconstruct the target list.** Are the sprayed accounts alphabetical, from a
   public directory, from a LinkedIn scrape, from a prior breach? That tells you
   what the attacker has and whether more is coming.

## Containment

- **Reset passwords** for every account with a valid-password result code, and
  **revoke sessions** (`Revoke-MgUserSignInSession`) — a reset alone does not kill
  live refresh tokens.
- **Block the source** IPs/ASNs via named locations in conditional access.
- **Re-register MFA** for affected accounts if any new method appeared.
- **Enable Continuous Access Evaluation** so revocation propagates in near-real
  time instead of on token expiry.

## Hardening — in order of how much it actually helps

1. **Block legacy authentication.** One conditional access policy. This removes
   the primary spray path and is the highest-value single change available.
2. **Phishing-resistant MFA** — FIDO2 or Windows Hello for Business. Push-based
   MFA is defeated by fatigue attacks; enable number matching at minimum.
3. **Entra Password Protection** with a custom banned-password list — company
   name, local sports teams, `Season+Year`. Extend it to on-prem DCs with the
   agent. Spray runs use exactly these.
4. **Conditional access baseline**: block unknown geographies, require compliant
   or hybrid-joined devices, sign-in risk policies.
5. **Smart lockout** tuned — but understand it is a mitigation, not a detection:
   attackers pace *under* it deliberately.
6. **Remove the account attack surface** — disable unused accounts, review
   service accounts for interactive sign-in capability, and check that break-glass
   accounts are excluded from CA policies but monitored aggressively.

## One thing worth flagging to leadership

If any account showed 50076 (MFA required, password correct), that password is
known to an attacker and is very likely reused elsewhere — on personal accounts
and on systems outside Entra's protection. The incident does not end at the tenant
boundary, and the reset scope should reflect that.
