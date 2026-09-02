---
prompt_id: 16
category: Network security
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

Explain how to detect command-and-control beaconing using NetFlow data when packet payloads are unavailable.

## Response

## Why this works without payloads

You cannot read the content, but you do not need to. Beaconing is a **timing and
volume** signature, and NetFlow preserves both. An implant checking in on a
schedule produces a pattern no human browsing session produces: regular
intervals, consistent small payloads, and a session that outlives any plausible
user activity.

Encryption changes nothing here. TLS hides the payload; it does not hide *when*
you sent it or *how much*.

## The core signal: interval regularity

Group flows by `(src_ip, dst_ip, dst_port)` and compute the deltas between
consecutive connection start times. Then measure how *regular* those deltas are.

**Coefficient of variation** is the workhorse:

```
CV = stddev(deltas) / mean(deltas)
```

- **CV < 0.1** — near-perfect periodicity. Almost certainly automated.
- **CV 0.1–0.3** — jittered beacon. Still highly suspicious.
- **CV > 1.0** — human-driven or bursty. Normal browsing sits here.

The trap: **plenty of benign traffic is also periodic.** Software update checks,
NTP, monitoring agents, telemetry, mail polling. Periodicity alone is not
malicious; it is the starting filter, not the verdict.

## Handling jitter

Mature frameworks (Cobalt Strike, Sliver, Mythic) randomise the sleep interval —
typically ±10–50%. This breaks naive CV thresholds, so use methods that tolerate
spread:

**MAD (median absolute deviation)** instead of standard deviation — far less
sensitive to a few outlying gaps caused by a laptop sleeping.

**Interval bucketing.** Round deltas to the nearest 5 or 10 seconds and count
the mode's share. A 60-second beacon with 30% jitter still clusters heavily
around one bucket.

**Fourier / autocorrelation.** Transform the connection timestamps into a time
series and look for a dominant frequency. This detects periodicity that
survives substantial jitter, at higher compute cost.

**Cobalt Strike specifically:** the default 60-second sleep with 0% jitter is
trivially caught. Tuned profiles with long sleeps (hours) and high jitter are
much harder — which is why interval analysis needs a long observation window,
7–30 days, not one day.

## Supporting signals — these are what make it precise

**Payload size consistency.** A beacon check-in with no tasking returns an
almost identical byte count every time. Compute the standard deviation of
`bytes_out` per flow group; near-zero variance across dozens of connections is
extremely unusual for real applications.

**Bytes-out to bytes-in ratio.** Normal web browsing is heavily inbound (you
request a little, receive a lot). A beacon is roughly symmetric and small. A
sustained *outbound-heavy* ratio suggests exfiltration rather than beaconing.

**Session duration and count.** Hundreds of short connections to one destination
over days, from one internal host.

**Connection persistence past working hours.** A workstation talking to one
external IP at 03:00, every day, while the user is not logged in.

**Destination rarity.** How many other internal hosts talk to this destination?
A single host with an exclusive relationship to an external IP is far more
interesting than one shared across the estate.

**Long-lived flows on odd ports**, or well-known ports carrying the wrong
protocol shape.

## A practical scoring approach

```sql
SELECT src_ip, dst_ip, dst_port,
       COUNT(*)                                  AS connections,
       STDDEV(delta) / NULLIF(AVG(delta),0)      AS cv,
       STDDEV(bytes_out)                         AS byte_variance,
       AVG(bytes_out) / NULLIF(AVG(bytes_in),0)  AS ratio,
       COUNT(DISTINCT DATE(start_time))          AS active_days
FROM flow_deltas
GROUP BY src_ip, dst_ip, dst_port
HAVING connections >= 24
   AND active_days >= 3
   AND cv < 0.35
   AND byte_variance < 200
ORDER BY cv ASC
```

Require **all** of: enough connections to be statistically meaningful, presence
across multiple days, low interval variance, and low size variance. Any one
alone floods you; the conjunction is precise.

## Enrichment before alerting

Do not alert straight off the statistics. Enrich with what you have:

- **Domain age** — newly registered domains are strongly suspicious
- **ASN and hosting provider** — bulletproof hosting, or a residential proxy
- **Threat intel** on the destination IP
- **JA3/JA4** if you have any TLS metadata, even without payload
- **Asset context** — which host, whose, what role
- **Process attribution** from EDR — *which process* opened the connection is
  often the fastest way to a verdict

## Tuning, honestly

The false positive list is predictable and long: OS and application update
checks, antivirus definition polling, monitoring and RMM agents, cloud sync
clients, telemetry, mail clients, NTP, certificate revocation checks.

**Build an allow-list by destination and process**, and expect to spend real
time on it. This is the reason beaconing detection projects fail — not the maths,
which is straightforward, but the tuning, which is continuous and unglamorous.

Baseline for at least a week before enabling alerts, and re-baseline after any
significant change to the software estate.

## Limitations to be clear about

- **Very long sleep intervals** (12–24h) need weeks of data and may never reach
  statistical confidence.
- **Traffic through a corporate proxy** may collapse all internal sources to one
  IP unless you have the proxy logs to re-attribute them.
- **Domain fronting and CDN-hosted C2** put the beacon behind an IP your estate
  legitimately talks to constantly.
- **NAT** obscures the true internal source without additional correlation.

None of these make the approach useless — they define where it needs to be
paired with endpoint telemetry rather than relied on alone.
