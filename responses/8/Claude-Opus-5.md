---
prompt_id: 8
category: Reasoning / planning
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

A security team has 6 analysts. Each analyst works 8-hour shifts. The SOC must be staffed 24 hours a day with at least 2 analysts at all times. What is the minimum number of shifts needed per day and how could the schedule be organized?

## Response

## The arithmetic

**Minimum shifts per day: 3.**

24 hours of coverage ÷ 8-hour shifts = 3 consecutive shift blocks. That is the
number of *time blocks*, and it's the answer to the question as asked.

The number that trips people up is the second one:

**Minimum analyst-shifts per day: 6.** Three blocks × 2 analysts per block.

These are different quantities and conflating them is the usual error. "Three
shifts" describes the clock. "Six analyst-shifts" describes the labour. With
exactly 6 analysts each working one 8-hour shift, the two happen to line up at
6 = 6, which is why the problem is solvable at all — and why it's solvable with
*zero* slack.

## The schedule

| Shift | Hours | Analysts |
|---|---|---|
| Day | 08:00 – 16:00 | A1, A2 |
| Swing | 16:00 – 00:00 | A3, A4 |
| Night | 00:00 – 08:00 | A5, A6 |

Total: 6 analysts × 8 hours = 48 analyst-hours = 24 hours × 2 analysts. Exactly
balanced.

## Why this schedule does not survive contact with a real SOC

The maths works. The roster does not, and it's worth being explicit about why,
because "6 analysts covers 24×7 with 2-up" is a genuinely dangerous conclusion to
hand a manager.

**1. It assumes a 7-day week from every analyst.** Six analysts covering 21 shifts
a week (3 shifts × 7 days) means 3.5 shifts each — but the table above assigns
each analyst the *same shift every single day*, with no days off. A real week
needs 21 shift-slots filled from a pool working ~5 days each, which is 21 ÷ 5 =
4.2 → **you need at least 9 analysts for sustainable 24/7 two-up coverage**, and
in practice 10–12 once you account for the items below.

**2. Zero absence tolerance.** One analyst on PTO, sick, in training, or in
court/IR overrun and the minimum-2 constraint is breached immediately. There is no
float.

**3. No handover time.** Shifts that abut exactly at 16:00 mean the outgoing pair
walks as the incoming pair sits down. Real rosters overlap 15–30 minutes, which
adds analyst-hours.

**4. Night shift attrition.** A permanent night assignment for A5 and A6 with no
rotation is one of the more reliable ways to lose two analysts.

## What I'd actually propose

**Option A — Rotating 4-on/4-off, 12-hour shifts (2 blocks/day).**
Four teams of 2. Each team works 4 days then 4 off, alternating day/night blocks
on a longer cycle. Covers 24/7 with 2-up, gives predictable long breaks, and 8
analysts is enough. Widely used in SOCs and in emergency services generally. Costs
you the 12-hour fatigue curve on the back half of a night shift.

**Option B — Keep 8-hour shifts, staff to 9–10.**
Three blocks, 2-up minimum, with 3–4 analysts as float across the week. Rotate
through day/swing/night on a fixed cycle (forward rotation — day → swing → night —
is easier on circadian adjustment than backward). More headcount, better fatigue
outcomes, and it survives one person being out.

**Option C — Follow-the-sun, if you have the geography.**
Two or three sites in different time zones, each running normal business-hours
shifts. Eliminates night work entirely. Only available if the org already has the
footprint.

## The honest answer to the question asked

- **Minimum shifts per day: 3** (three 8-hour blocks)
- **Minimum analyst-shifts per day: 6** (2 per block)
- **Analysts needed to actually run it: 9+**, not 6

If this is an exam question, the expected answer is 3 shifts with 2 analysts each.
If it's a staffing plan, 6 analysts is roughly 60% of what the coverage model
requires, and I'd push back before it's committed to a budget.
