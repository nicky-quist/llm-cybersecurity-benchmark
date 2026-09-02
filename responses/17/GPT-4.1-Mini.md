---
prompt_id: 17
category: Identity security
model: GPT-4.1-Mini
vendor: OpenAI
api_id: gpt-4.1-mini-2025-04-14
collected_utc: 2026-09-01T23:10:00Z
collected_via: manual-paste
source: lmarena.ai (Side by Side)
collection_caveat: >
  Pasted from LMArena's side-by-side view; formatting partially lost in transit.
  LMArena displayed the pinned snapshot gpt-4.1-mini-2025-04-14 and does not
  expose sampling parameters.
---

## Prompt

A company suspects password spraying against Microsoft Entra ID. Describe detection logic, triage steps, and hardening actions.

## Response

Certainly! Password spraying against Microsoft Entra ID (formerly Azure AD) is a common attack where the attacker tries a few common passwords across many accounts to avoid lockout. Here's how a SOC team can detect, triage, and harden defenses against this attack type.

**1. Detection Logic**

*Key Indicators of Password Spraying*

- Multiple failed sign-in attempts for many distinct accounts within a short time window.
- Failed attempts usually come from a limited set of IP addresses or geographic regions.
- Use of low-frequency, low-volume login attempts per account (to avoid lockouts).
- Successful sign-ins immediately following multiple failures.
- Sign-ins that deviate from typical user behavior (e.g., unusual device types, locations, or times).

*How to Detect in Microsoft Entra ID*

- Use Azure AD Sign-in Logs (available via Azure Portal, Azure Sentinel, or Microsoft Graph API).
- Look for patterns:
  - Many "Failure" sign-ins with "InvalidPassword" or "BadPassword" error codes.
  - High number of distinct users showing failed attempts from the same IP or region.
  - Signs of impossible travel or new device usage following failed login attempts.

*Sample Detection Rule (Conceptual)*

Alert when:
- Number of failed login attempts using different usernames from same IP or geo-location exceeds a threshold (e.g., > 10 within 10 minutes).
- AND the failure reason is "InvalidPassword" or equivalent.

In Azure Sentinel, this might be a KQL query like:

```kql
SigninLogs
| where ResultType == "50053" or ResultType == "50055"  // BadPassword-related errors
| summarize FailedAttempts = count(), DistinctUsers = dcount(UserPrincipalName) by IPAddress, bin(TimeGenerated, 15m)
| where FailedAttempts > 10 and DistinctUsers > 5
```

**2. Triage Steps**

*Step 1: Confirm the Attack*
- Review sign-in logs correlated with threat intelligence.
- Identify the source IP addresses or ranges.
- Check if any accounts show successful logins shortly after failed attempts (may indicate compromised accounts).

*Step 2: Identify Scope and Impact*
- Map out targeted accounts.
- Categorize based on criticality / privilege levels (e.g., admin accounts).
- Identify any sign-ins from suspicious locations or devices.
- Check related logs for anomalous post-login behavior (e.g., password changes, creating forwarding rules).

*Step 3: Prevent Further Damage*
- Temporarily block suspicious IP addresses or regions via Conditional Access or network controls.
- Notify impacted account owners to verify any suspicious activity.

*Step 4: Investigate Potential Account Compromise*
- Look for successful logins bypassing MFA (if present).
- Review mailbox audit logs or other app logs for suspicious activity.
- If compromise is confirmed, initiate incident response and account recovery.

**3. Hardening Actions**

*A. Immediate Mitigation*
- Enable and enforce Multi-Factor Authentication (MFA) for all users, esp. privileged accounts.
- Implement Conditional Access Policies restricting sign-in based on:
  - Trusted locations (IP allowlists)
  - Device compliance (Intune)
  - Risk levels calculated by Azure AD Identity Protection
- Set up user risk policies to require remediation on suspicious activity.

*B. Improve Password Hygiene*
- Enforce strong password policies and prohibit common passwords or ones found in password spray dictionaries.
- Use Azure AD Password Protection to block weak or leaked passwords.
- Require periodic password changes or use passwordless authentication methods (FIDO2, Windows Hello).

*C. Continuous Monitoring*
- Enable Azure AD Identity Protection with automated risk detection.
- Integrate logs with a SIEM (Azure Sentinel recommended) for advanced correlation and alerting.
- Monitor anomalous activities such as impossible travel, unfamiliar sign-in properties, or risky sign-in indicators.

**Summary Table**

| Category | Key Actions |
|---|---|
| Detection | Analyze Azure AD sign-in logs for multiple failed logins from same IP targeting many users; detect invalid password errors. |
| Triage | Confirm attack, identify source IPs/users targeted, check for successful compromised logins, block offenders temporarily. |
| Hardening | Enforce MFA and Conditional Access, use Azure AD Password Protection, monitor via Azure Sentinel/Identity Protection. |

If you want, I can help create sample Conditional Access policies or provide KQL queries tailored for your environment. Would that be helpful?
