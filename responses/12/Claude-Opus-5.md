---
prompt_id: 12
category: Cloud security
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

An alert shows an unusual AWS IAM access key usage from a new geography. Describe investigation and containment steps for a cloud-focused SOC team.

## Response

## First: decide whether to contain before you finish investigating

The instinct is to investigate first. For a long-lived IAM access key seen from a
new geography, that instinct is usually wrong. Key compromise moves fast — the
common pattern is credential theft, then enumeration, then persistence, then
either resource abuse (crypto mining) or exfiltration, inside 15–30 minutes.

**Contain immediately if any of these are true:**
- the key belongs to a human user rather than a service
- you see `iam:Create*`, `iam:Attach*`, `iam:PutUserPolicy`, or `CreateAccessKey`
- you see `GetSecretValue`, `Decrypt`, `AssumeRole` into other accounts
- there's a `GetCallerIdentity` immediately followed by broad `List*`/`Describe*`
- the source is a known VPN/Tor exit or a cloud provider's IP space

Otherwise investigate for 10 minutes first, because a false containment on a
production service key is its own incident.

## Triage — is this actually anomalous?

Geography alone is a weak signal. Rule out the boring explanations first:

- **Is the user travelling?** Check with them, or the HR/travel system.
- **Is it a VPN or a new corporate egress?** Compare against your egress ranges.
- **Is it AWS infrastructure?** Cross-region service calls, SDK retries through a
  different endpoint, or a CI runner in a new region all look "foreign".
- **Is the key on a service account?** Service credentials shouldn't move
  geography at all — for those, a new geography is a much stronger signal than for
  a human user.

Key CloudTrail fields for this: `sourceIPAddress`, `userAgent`,
`userIdentity.type` / `.arn` / `.accessKeyId`, `tlsDetails`, and
`additionalEventData`. The `userAgent` is often the tell — `aws-cli/2.x` from a
key that has only ever been used by `Boto3/1.x` inside a Lambda is a different
operator.

## Investigation

**1. Scope the key's activity.** Pull every CloudTrail event for that
`accessKeyId` across all regions and both management and data events. Attackers
enumerate in regions you don't use precisely because nobody looks there.

```
fields @timestamp, eventName, sourceIPAddress, awsRegion, errorCode, userAgent
| filter userIdentity.accessKeyId = "AKIA..."
| sort @timestamp asc
```

**2. Build the timeline and find first-seen.** The first anomalous call is your
approximate compromise time. Everything before it is baseline; everything after
is in scope.

**3. Look specifically for these, in order:**
- `GetCallerIdentity`, `ListBuckets`, `DescribeInstances`, `ListUsers` —
  orientation, and a strong sign of a human operator
- `CreateAccessKey`, `CreateUser`, `AttachUserPolicy`, `CreateLoginProfile`,
  `UpdateAssumeRolePolicy` — **persistence**, and the reason rotating one key is
  often insufficient
- `AssumeRole` — lateral movement, possibly cross-account. Follow every one.
- `GetObject` volume and `GetSecretValue` / `kms:Decrypt` — exfiltration
- `RunInstances` (large types, unusual regions), `CreateFunction` — resource abuse
- `StopLogging`, `DeleteTrail`, `PutEventSelectors`, `DeleteFlowLogs` —
  **anti-forensics.** If you see these, assume everything after is unlogged.

**4. Establish blast radius.** What does this principal actually have? Resolve
attached policies, inline policies, group memberships, and — critically — every
role it can assume, transitively. IAM Access Analyzer and `aws iam
simulate-principal-policy` beat reading JSON by hand.

**5. Find the source of the leak.** Keys don't leak from AWS. Check: committed to
a repo (GitHub secret scanning, `trufflehog` over history), in a CI variable, in a
Terraform state file, in a container image layer, on a compromised laptop, or in a
Slack message. If you don't find the source, you'll rotate and get popped again.

## Containment

Order matters here.

1. **Deactivate, don't delete.** `aws iam update-access-key --status Inactive`.
   Deleting destroys evidence and breaks attribution for the events you're still
   analysing. Deactivation is immediate and reversible.
2. **Apply an explicit deny.** If the key is on a role or you need to cut a
   session that's already assumed, attach an inline `Deny *` policy or use
   `AWSRevokeOlderSessions` — deactivating a key does **not** kill STS tokens
   already issued from it. This is the step most often missed: temporary
   credentials can outlive the key that minted them by up to 12 hours.
3. **Rotate every key for that principal**, not just the alerting one.
4. **Remove attacker persistence.** Delete any IAM users, keys, login profiles,
   or policies created during the incident window. Check trust policies on roles
   for added external principals.
5. **Preserve evidence.** Snapshot affected EC2 volumes, export the relevant
   CloudTrail range to a separate account, capture VPC Flow Logs and GuardDuty
   findings before retention windows close.
6. **Quarantine touched resources** — security-group isolation for instances, not
   termination, until forensics is done.

## Recovery and hardening

- **Eliminate the key.** The durable fix for a long-lived access key is not to
  have one: IAM Roles Anywhere, IRSA for EKS, instance profiles for EC2, OIDC
  federation for GitHub Actions. Every one of those removes a static secret.
- **Enforce SCPs** denying IAM changes and CloudTrail modification outside a
  break-glass role, and denying regions you don't operate in.
- **Condition policies on source** — `aws:SourceIp`, `aws:VpcSourceIp`, or
  `aws:PrincipalOrgID`.
- **Turn on** GuardDuty (the `UnauthorizedAccess:IAMUser/*` and
  `CredentialAccess` families cover exactly this), CloudTrail org-wide with log
  file validation, and S3 Access Logging.
- **Automate the first response.** An EventBridge rule on GuardDuty →
  Lambda that deactivates the key and opens the ticket takes containment from
  minutes to seconds, which is the whole game here.

## What I'd want written down afterwards

Time to detect, time to contain, whether STS sessions were revoked or just the
key, how the key leaked, and how many other long-lived keys exist in the account
today. That last number is the one that predicts whether this recurs.
