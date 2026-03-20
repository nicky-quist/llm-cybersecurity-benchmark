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

## Suggested future improvements

- Expand to 30-50 prompts
- Use a numeric rubric (accuracy, depth, clarity, hallucination resistance)
- Normalize the model pool so each model sees similar categories
- Add inter-rater review or blinded scoring
- Export all raw responses for reproducibility
