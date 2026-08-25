# LLM Evaluation for Cybersecurity SOC Tasks

A benchmarking project comparing different large language models on cybersecurity and SOC-oriented tasks using **Handshake AI Versus** pairwise comparisons.

**[Live dashboard →](https://nicky-quist.github.io/llm-cybersecurity-benchmark/dashboard/index.html)**

## Project Goal

This project evaluates how different LLMs perform on technical tasks that matter in SOC and security engineering workflows, including:

- MITRE ATT&CK explanation
- SOC detection guidance
- incident investigation
- detection engineering
- Python scripting
- threat intelligence concepts
- anomaly detection for cyber
- hallucination resistance
- cloud and identity security workflows
- security automation and incident communication

Rather than claiming broad model superiority, this project explores whether **different models perform better on different cybersecurity task types**.

## AI SOC Copilot — extending the benchmark into a live tool

**[copilot/](copilot/)** takes this project's evaluation muscle and applies it to a real alert instead of a static prompt: given a triaged alert (in [soc-triage-tool](https://github.com/nicky-quist/soc-triage-tool)'s output schema), it retrieves MITRE ATT&CK and live CVE/NVD context, then uses Claude to recommend a next action with an explicit explainability rationale. Runs with zero configuration — no API key required to see the full pipeline execute. See [copilot/README.md](copilot/README.md) for the design and a usage example.

## Methodology

- Platform: Handshake AI Versus
- Evaluation design: pairwise model comparisons
- Number of prompts: 20
- Domains tested:
  - cybersecurity knowledge
  - SOC detection and IR
  - detection engineering
  - coding
  - reasoning and planning
  - hallucination handling
  - cloud/identity/network security
  - security operations strategy

Each comparison was judged on a blend of:

- technical correctness
- completeness
- operational usefulness
- clarity
- realism for SOC workflows
- hallucination resistance when relevant

## Results

Eight models, twenty pairwise comparisons. Every number below is regenerated from
`data/prompt_results.csv` by `analysis/statistics.py` — none of it is maintained by hand.

![Win rate by model with 95% Wilson intervals](visualizations/wins_by_model.png)

### Per model

Win rate with a 95% Wilson score interval. **Appearances are shown because raw win
counts are not comparable across models drawn a different number of times** — GPT-4.1-Mini
and Gemini-2.5-Pro both have 4 wins, from 7 and 5 appearances respectively.

| Model | Appearances | W | L | Win rate | 95% CI |
|---|---:|---:|---:|---:|---|
| Gemini-2.5-Pro | 5 | 4 | 1 | 80% | 38%–96% |
| Gemini-3.1-Pro-Preview | 5 | 4 | 1 | 80% | 38%–96% |
| GPT-5.2 | 4 | 3 | 1 | 75% | 30%–95% |
| GPT-5.2-High | 3 | 2 | 1 | 67% | 21%–94% |
| GPT-4.1-Mini | 7 | 4 | 3 | 57% | 25%–84% |
| Gemini-2.5-Flash-Lite | 5 | 2 | 3 | 40% | 12%–77% |
| Gemini-3-Flash-Preview | 5 | 1 | 4 | 20% | 4%–62% |
| **GPT-4o** | **6** | **0** | **6** | **0%** | **0%–39%** |

Every interval is enormous — the widest spans 73 points. At three to seven appearances
per model that is the honest precision of this design, and it does not resolve the ordering.

### Vendor split

| Vendor | Wins | Win rate | 95% CI |
|---|---:|---:|---|
| Google | 11/20 | 55% | 34%–74% |
| OpenAI | 9/20 | 45% | 26%–66% |

Exact two-sided binomial test against a 50/50 null: **p = 0.82**. An 11–9 split is what a
fair coin produces routinely over twenty flips. This is not evidence that either vendor
is better at security tasks, and an earlier version of this README presented it as though
it were.

![Bradley-Terry strengths with bootstrap intervals](visualizations/bradley_terry.png)

### Bradley-Terry strengths

The standard model for paired-comparison data: `P(i beats j) = sᵢ / (sᵢ + sⱼ)`, fitted by
maximum likelihood, with bootstrap intervals over 2000 resamples. 1.0 is average.

| Model | Strength | 95% CI | Separated from parity? |
|---|---:|---|---|
| Gemini-2.5-Pro | 2.14 | 0.42–4.07 | no |
| GPT-5.2-High | 2.00 | 0.33–4.20 | no |
| GPT-5.2 | 1.22 | 0.08–3.98 | no |
| Gemini-3.1-Pro-Preview | 1.09 | 0.20–3.20 | no |
| GPT-4.1-Mini | 0.71 | 0.12–3.12 | no |
| Gemini-2.5-Flash-Lite | 0.47 | 0.07–1.74 | no |
| Gemini-3-Flash-Preview | 0.29 | 0.02–1.42 | no |
| **GPT-4o** | **0.08** | **0.02–0.26** | **yes** |

### What this data actually supports

**One finding, and it is not the one that was being reported.**

- **GPT-4o lost all six of its comparisons.** It is the only model whose interval excludes
  parity, and therefore the only result here that survives contact with a significance test.
- **Nothing separates the other seven.** Every one of their Bradley-Terry intervals overlaps
  1.0. The leaderboard ordering is real in the sense that someone recorded those judgements,
  and meaningless in the sense that it would likely reshuffle on a rerun.
- **The vendor comparison is a coin flip** (p = 0.82).
- The task-specific framing — that different models suit different SOC tasks — remains a
  reasonable *hypothesis*. Twenty comparisons cannot test it. It needs per-category sample
  sizes, and each category here has one or two.

**GPT-4o was missing from this repository's results entirely.** `model_wins.csv` was
maintained by hand and only listed models with at least one win, so the single model that
lost every matchup — the one genuinely significant finding in the dataset — did not appear
in the results table, the README, or the dashboard chart. The derived CSVs are now generated
from source by `analysis/statistics.py`, and a test asserts that every model appearing in
any comparison also appears in the output.

### Reproducing

```bash
python analysis/statistics.py            # the full report
python analysis/statistics.py --write    # regenerate data/model_wins.csv, data/vendor_wins.csv
python analysis/make_visualizations.py   # regenerate the charts
python -m unittest discover -s tests -t .
```

## Repository Structure

```text
llm-cybersecurity-benchmark/
├── README.md
├── dashboard/
│   └── index.html
├── data/
│   ├── prompt_results.csv
│   ├── model_wins.csv
│   └── vendor_wins.csv
├── analysis/
│   ├── statistics.py           # Wilson intervals, binomial test, Bradley-Terry
│   └── make_visualizations.py  # regenerates visualizations/ from source
├── tests/                      # regression tests on the reporting pipeline
├── copilot/
│   ├── README.md
│   ├── soc_copilot.py
│   ├── attack_context.py
│   ├── cve_context.py
│   ├── llm_client.py
│   ├── run_demo.py
│   └── sample_alerts.json
└── visualizations/
    ├── wins_by_model.png       # win rate + Wilson intervals
    ├── bradley_terry.png       # strengths + bootstrap intervals
    ├── wins_by_vendor.png
    └── winner_by_prompt.png
```


## Interactive Dashboard Features

The dashboard (`dashboard/index.html`) now includes:

- KPI cards for prompt count, vendor wins, model coverage, and top model ties
- Dual scoreboards (wins by vendor + all models by win rate, labelled wins/appearances)
- A standing caveat on the scoreboard stating the significance of what is plotted
- Category chips, full-text search, and sortable prompt result rows
- Expand/collapse rationale details per prompt
- Model spotlight cards with appearances, win/loss, win rate and a 95% Wilson interval
- Head-to-head matchup summaries showing repeated pair outcomes

Open `dashboard/index.html` in a browser to explore the full interactive view.

## Prompt Set

The full prompt set is stored in `data/prompt_results.csv` (20 rows).

## Limitations

These are the reasons the results above are hedged as heavily as they are.

- **n = 20 is too small to rank eight models.** Each appears three to seven times. The
  confidence intervals in the results section are the honest width, not a formality.
- **A single unblinded judge.** I scored every comparison myself, knowing which model was
  which. There is no second rater and therefore no inter-rater agreement to report. Knowing
  the model identity is a live route for bias, and nothing here controls for it.
- **Unbalanced pairings.** Not a round robin. Strength of schedule varies: GPT-4o drew a
  Gemini opponent in all six of its comparisons, so its 0–6 is partly a statement about who
  it faced. It is the only significant result here and it still carries that caveat.
- **One comparison per prompt.** No repeats, so within-prompt judging variance is unmeasured.
- **Raw model outputs were not archived**, so the judgements cannot be independently re-scored.
  That is the single biggest obstacle to anyone reproducing this, and the first thing to fix.
- **Category-level claims are unsupported.** Twenty prompts across twenty categories is one
  observation each.

## Why this project matters

For security teams, LLM adoption is not just about "best model overall." It is about **fit for purpose**:

- Which model explains ATT&CK techniques best?
- Which model gives the most realistic SOC workflow guidance?
- Which model is strongest at coding or analytics tasks?
- Which model behaves safely on hallucination tests?

This repo shows one lightweight way to evaluate those questions and iterate with more evidence over time.
