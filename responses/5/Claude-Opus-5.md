---
prompt_id: 5
category: Python coding
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

Write a Python script that analyzes a web server log file and detects IP addresses that made more than 20 failed login attempts within a 10 minute period. Explain how the script works.

## Response

```python
#!/usr/bin/env python3
"""Detect IPs exceeding a failed-login threshold inside a sliding time window.

    python failed_logins.py access.log
    python failed_logins.py access.log --threshold 20 --window 10 --header x-forwarded-for
"""
import argparse
import collections
import re
import sys
from datetime import datetime, timedelta

# Common Log Format / Combined:
#   1.2.3.4 - - [10/Oct/2025:13:55:36 -0700] "POST /login HTTP/1.1" 401 2326 ...
LINE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)[^"]*"\s+(?P<status>\d{3})'
)
TS_FORMAT = "%d/%b/%Y:%H:%M:%S %z"

# A failed login is a request to an auth endpoint that came back unauthorised.
# Status alone is too broad: 401 on a probed admin path is not a login attempt.
FAILURE_STATUSES = {401, 403}
AUTH_PATHS = re.compile(r"/(login|signin|session|auth|oauth/token|wp-login\.php)", re.I)


def parse(line):
    m = LINE.match(line)
    if not m:
        return None
    try:
        ts = datetime.strptime(m.group("ts"), TS_FORMAT)
    except ValueError:
        return None
    return ts, m.group("ip"), int(m.group("status")), m.group("path")


def is_failed_login(status, path):
    return status in FAILURE_STATUSES and AUTH_PATHS.search(path) is not None


def detect(lines, threshold=20, window_minutes=10):
    """Sliding window per IP. Yields (ip, count, first_ts, last_ts) on trigger."""
    window = timedelta(minutes=window_minutes)
    attempts = collections.defaultdict(collections.deque)
    reported = {}
    malformed = 0

    for line in lines:
        parsed = parse(line)
        if parsed is None:
            malformed += 1
            continue
        ts, ip, status, path = parsed
        if not is_failed_login(status, path):
            continue

        q = attempts[ip]
        q.append(ts)
        # Evict anything now outside the window. Each timestamp is appended once
        # and popped once, so the whole pass is O(n), not O(n * window).
        while q and ts - q[0] > window:
            q.popleft()

        if len(q) > threshold:
            # Report the worst burst per IP rather than one alert per line.
            best = reported.get(ip)
            if best is None or len(q) > best[0]:
                reported[ip] = (len(q), q[0], q[-1])

    return reported, malformed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("logfile")
    p.add_argument("--threshold", type=int, default=20)
    p.add_argument("--window", type=int, default=10, help="minutes")
    p.add_argument("--header", help="treat this header field as the client IP (e.g. x-forwarded-for)")
    args = p.parse_args()

    with open(args.logfile, encoding="utf-8", errors="replace") as f:
        hits, malformed = detect(f, args.threshold, args.window)

    if malformed:
        print(f"# {malformed} lines did not parse — check the log format", file=sys.stderr)

    if not hits:
        print(f"No IP exceeded {args.threshold} failed logins in {args.window} minutes.")
        return 0

    print(f"{'ip':<40}{'count':>7}   window")
    for ip, (count, first, last) in sorted(hits.items(), key=lambda kv: -kv[1][0]):
        span = (last - first).total_seconds()
        print(f"{ip:<40}{count:>7}   {first:%H:%M:%S}–{last:%H:%M:%S} ({span:.0f}s)")
    return 1        # non-zero so this can gate a cron job or CI step


if __name__ == "__main__":
    raise SystemExit(main())
```

## How it works

**Parsing.** One regex against Common/Combined Log Format pulls IP, timestamp,
status and path. Unparseable lines are counted and reported to stderr rather than
silently dropped — a log-format mismatch that silently yields zero detections is
worse than a crash, because it looks like a clean result.

**Defining "failed login".** Status code alone is too loose. A 401 on
`/api/internal/metrics` is a scanner probing, not a login attempt, and counting it
inflates every number. The script requires *both* an auth-ish path and a 401/403.
`AUTH_PATHS` is the first thing you should tune to your application — this is
where the false positives live.

**The sliding window.** Each IP gets a `deque` of failure timestamps. On every new
failure, timestamps older than `now - window` are popped from the left. Because
each timestamp is appended once and popped at most once, the whole file is a
single O(n) pass with memory bounded by the busiest window, not by file size. That
matters: the naive approach — for each event, scan backwards over all prior events
— is O(n²) and dies on a real access log.

Note this is a true **sliding** window, not a fixed bucket. Fixed 10-minute
buckets miss an attacker who puts 15 attempts at 09:09 and 15 at 09:11: neither
bucket exceeds 20, but the sliding window sees 30 in two minutes.

**Reporting.** One line per offending IP showing its worst burst, sorted by
severity, rather than an alert per log line. Exit code 1 on detection so it can
gate a cron job.

## Caveats worth stating before this goes anywhere near production

- **Proxies and CDNs.** If traffic passes through a load balancer or Cloudflare,
  the first field is the proxy's IP and every attacker collapses into one entry.
  You need `X-Forwarded-For` — hence the `--header` flag, which is stubbed here
  and needs the combined-format regex extended to capture it. Trust only the hop
  your own edge appends; the client controls the rest of that header.
- **Timezones.** `%z` is parsed, so comparisons are timezone-aware and correct
  across a DST boundary. Logs written without an offset will fail to parse — that
  is deliberate rather than silently assuming UTC.
- **Out-of-order lines.** The eviction assumes roughly monotonic timestamps. Merged
  logs from multiple hosts can interleave; sort by timestamp first if so.
- **What this does not catch.** Low-and-slow credential stuffing (3 attempts/hour
  across 10,000 IPs) is invisible to a per-IP threshold. That is a *password
  spraying* detection — pivot on failures per *account* and on distinct-IPs-per-
  account, not failures per IP. The two detections are complementary and you want
  both.
- **Success after failures.** The genuinely urgent signal is 20 failures followed
  by a 200. Worth adding as a separate, higher-severity rule.
