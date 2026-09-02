# Methodology Notes

## Evaluation approach

This project used pairwise human evaluation rather than an automated benchmark suite.

For each prompt:
1. Two models were compared side by side in Handshake AI Versus.
2. Responses were reviewed for correctness, completeness, clarity, and SOC usefulness.
3. A single winner was selected.
4. Notes were recorded explaining the decision.

## Why pairwise comparison?

Handshake AI Versus presents two models at a time, which makes pairwise comparison the most natural study design.

Benefits:
- easy direct comparison
- practical for small experiments
- useful for qualitative evaluation

Tradeoffs:
- not all models face the same opponents
- results are sensitive to matchup selection
- pairwise wins do not imply universal ranking

## Round two

Handshake AI Versus is no longer reachable, so round two runs on its own harness
(`harness/`). Each improvement below exists because round one's design made a
specific claim untestable — the mapping is one-to-one.

| Improvement | Why | Where |
|---|---|---|
| Balanced schedule, every model 6+ appearances | At 5 appearances a perfect record still gives p = 0.06. Six of eight models in round one were below that line, so their results were unfalsifiable before the first response was read. | `harness/schedule.py` |
| Blind A/B presentation, order fixed by seed | A single judge scored every round-one comparison knowing which model wrote which answer. Model identity is a live route for bias and nothing controlled for it. | `harness/judge.py` |
| Five-point rubric — correctness, completeness, usefulness, clarity, grounding | Round one recorded a winner and a sentence. A rubric makes the judgement decomposable and lets disagreement be located rather than just observed. | `harness/judge.py` |
| Raw responses archived before judging | Round one saved none, so no judgement can be independently re-scored. This is the single biggest obstacle to anyone reproducing the work. | `harness/collect.py` → `responses/` |
| Explicit model registry | Vendor used to be inferred from a prefix test on the model's name, which silently mislabels every model from a third vendor. | `data/models.csv` |
| Repeated pairings | With one comparison per pair, within-pair judging variance is unmeasured and every head-to-head record is a single coin flip. | `harness/schedule.py --repeats` |

Still open after round two — the *measurement* now exists for both of these; the
*data* does not, and no amount of tooling substitutes for collecting it:

- **A second rater.** `analysis/agreement.py` computes Cohen's kappa between judges,
  reported next to raw agreement so the kappa paradox is visible, plus an exact
  binomial test for position bias and a rubric-vs-verdict consistency rate. All of
  it returns "only one judge — no agreement to report" until a second person runs
  `python harness/judge.py --judge <their-name>` over the same pairings. Blinding
  removes identity bias; it says nothing about whether verdicts are reproducible.
- **Per-category claims.** `schedule.py --per-category 3` produces 60 comparisons
  with exactly three per category and models still balanced at 9–10 appearances.
  Until that schedule is actually run, the framing question — whether different
  models suit different SOC task types — remains a hypothesis this project poses
  rather than one it answers.
- **Automated judging** is deliberately not used. A model scoring a comparison
  containing its own output is self-preference bias. If added, it belongs alongside
  human scoring with the agreement rate reported, not in place of it.
