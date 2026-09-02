---
prompt_id: 17
category: Identity security
model: GPT-5.2
vendor: OpenAI
api_id: null
collected_utc: 2026-09-01T23:10:00Z
collected_via: manual-paste
source: lmarena.ai (Side by Side)
collection_caveat: >
  Pasted from LMArena's side-by-side view; formatting partially lost in transit.
  LMArena does not expose sampling parameters, so this is not drawn under the same
  conditions as an API response.
---

## Prompt

A company suspects password spraying against Microsoft Entra ID. Describe detection logic, triage steps, and hardening actions.

## Response

**Detection logic (what to look for in Microsoft Entra ID)**

*Primary signals (password spraying patterns)*

**Many users, same source, same app, short time window**

- High count of failed sign-ins for distinct usernames from a single IP / ASN / device fingerprint within 5–30 minutes.
- Often targets common entry points: Microsoft 365, Outlook, Exchange Online, Azure Portal, VPN SAML app, etc.

**Low-and-slow across many IPs**

- Same password attempted across many users is not directly visible, but you can infer it by:
  - Bursts of single/few failures per user across many users
  - Repeating cadence (e.g., every 30–60 minutes) to evade lockouts
- Distributed spraying may show as "many users failing from many IPs" but with shared User-Agent, same app, same geo/ASN, or similar device info.

**Failure reasons consistent with wrong password**

- Focus on sign-in result codes that indicate invalid credentials, not MFA prompts or conditional access blocks.
- In Entra sign-in logs, filter on Status = Failure and examine:
  - "Invalid username or password"
  - "Password expired" (sometimes appears during spray attempts)
- Exclude cases like "MFA required" or "Blocked by Conditional Access" (these can be downstream of a successful password guess, or just normal user friction—handle separately).

**Success following failures (spray "hit")**

A key high-fidelity pattern:

- A user has multiple recent failures from suspicious IP/geo → then a successful sign-in from same IP/UA/geo
- Or: success from a new geo/ASN immediately after many failures across the tenant.

**Risk signals (if using Entra ID Protection)**

- Alerts like Password spray, Atypical travel, Anonymous IP, Malicious IP, Unfamiliar sign-in properties.
- Correlate "Risky sign-in" and "Risky user" with failed sign-in spikes.

*Example analytic logic (SIEM / KQL-like pseudocode)*

**Single IP spraying many users**
- Window: 10 minutes
- Condition: failed_signins >= 30 AND distinct_users >= 20 from same ipAddress AND same appDisplayName

**User targeted from many IPs (distributed)**
- Window: 60 minutes
- Condition: for a given userPrincipalName, failures from distinct_ips >= 10 and distinct_geos >= 3

**Spray-hit correlation**
- For a given user or IP: failures followed by success within 0–30 minutes with shared ipAddress or userAgent or asn.

*Data sources*

- Entra ID Sign-in logs (interactive + non-interactive)
- Audit logs (for changes: MFA methods, Conditional Access, app consents)
- Identity Protection risk events (if licensed)
- M365 Defender (if integrated): AAD sign-in and risk correlations
- Firewall/VPN/Proxy logs (to attribute source IPs, confirm egress)

**Triage steps (SOC workflow)**

**1. Confirm it's spraying vs normal user issues**

- Check if failures cluster around: One IP/ASN/VPN provider; One app (e.g., Exchange Online); Many users in short time
- Compare to baselines: typical auth failure rates, known corporate VPN egress IPs, known scanners.

**2. Identify scope and "hits"**

- List: Top offending IPs/ASNs/geos; Targeted users (especially admins, finance, execs); Any successful sign-ins from suspicious sources
- For any suspected "hit," immediately review: Subsequent actions (mailbox access, file downloads, OAuth consent, token use); Sign-in method (legacy vs modern auth); Session details and device compliance

**3. Prioritize accounts**

Highest priority:
- Privileged roles (Global Admin, Privileged Role Admin, Exchange Admin, etc.)
- Users without MFA
- Users with recent password changes disabled/weak policy
- Shared/service accounts (should not be used interactively)

**4. Contain while preserving evidence**

For the source:
- Block IPs/ASNs via Conditional Access "Named locations" (where feasible) or network controls.
- If attacks come from many IPs, prefer risk-based controls over IP blocks alone.

For accounts at risk:
- Force password reset for suspected compromised accounts.
- Revoke sessions / refresh tokens (e.g., "Revoke sign-in sessions").
- Require MFA re-registration if you suspect MFA fatigue or method tampering.

Capture:
- Relevant sign-in log exports, timestamps, IPs, user agents, correlation IDs.

**5. Validate no persistence or follow-on compromise**

Check for:
- New MFA methods added or changed (Audit logs)
- New app registrations / service principals
- OAuth consent grants with high privileges
- Changes to Conditional Access, authentication methods policy, or security defaults
- Unusual mailbox rules, forwarding, eDiscovery searches (Exchange/Defender)

**Hardening actions (reduce likelihood and impact)**

*A. Enforce strong authentication*

- Require MFA for all users (prefer phishing-resistant)
  - Best: FIDO2 / Windows Hello for Business / Certificate-based auth
  - If using Authenticator: enable number matching and disable weaker prompts.
- Disable legacy authentication
  - Block IMAP/POP/SMTP AUTH and other legacy protocols that bypass modern controls.
  - Many spray campaigns target legacy endpoints.
- Use Conditional Access
  - Require MFA for: All cloud apps (or at least email + Azure portal); New device / unfamiliar location / risky sign-in
  - Require compliant or hybrid-joined device for sensitive apps.
  - Block sign-ins from high-risk countries not used by the business (careful with travelers).
  - Consider "Sign-in risk policy" (Identity Protection) to automatically require password change/MFA when risk is high.

*B. Reduce password spray effectiveness*

- Smart lockout: Ensure Entra smart lockout is enabled and tuned (it is on by default; verify behavior aligns with your environment).
- Ban weak passwords: Use Entra password protection (and on-prem password protection agents if hybrid).
- Eliminate shared accounts: Convert to workload identities / managed identities; ensure service accounts can't sign in interactively.

*C. Strengthen monitoring and response*

Alerting — create alerts for:
- High distinct-user failures per IP/ASN
- Successful sign-in after multiple failures
- Risky sign-in / risky user detections
- New MFA method added
- Conditional Access / auth policy changes

Automated response (SOAR):
- Auto-block IP (when confidence is high)
- Auto-disable sign-in / force reset for high-risk accounts
- Auto-revoke sessions for risky users

*D. Protect privileged access*

- Use Privileged Identity Management (PIM) with just-in-time elevation.
- Separate admin accounts; enforce stronger auth and stricter Conditional Access for admin portals.
- Block admin sign-in from non-managed devices and from the public internet where possible.

*E. User and helpdesk readiness*

- Train helpdesk to recognize spraying indicators and verify identity before password resets.
- Encourage users to report unexpected MFA prompts or sign-in notifications immediately.

If you tell me whether you have Entra ID P1/P2, whether the tenant is hybrid, and which apps are most targeted (Exchange/VPN/custom SAML), I can propose specific queries and threshold values tuned to your environment.
