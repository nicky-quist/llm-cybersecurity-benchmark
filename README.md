# LLM Evaluation for Cybersecurity SOC Tasks

A benchmarking project comparing different large language models on cybersecurity and SOC-oriented tasks using **Handshake AI Versus** pairwise comparisons.

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

## Final Results

### Wins by model

| Model | Wins |
|---|---:|
| Gemini-2.5-Pro | 4 |
| Gemini-3.1-Pro-Preview | 4 |
| GPT-4.1-Mini | 4 |
| GPT-5.2 | 3 |
| Gemini-2.5-Flash-Lite | 2 |
| GPT-5.2-High | 2 |
| Gemini-3-Flash-Preview | 1 |

### Wins by vendor

| Vendor | Wins |
|---|---:|
| Google | 11 |
| OpenAI | 9 |

### Key takeaways

- The expanded run still shows **no single model dominating every category**.
- Top performers are tightly clustered, with three models tied at 4 wins each.
- Google models led this sample overall (11/20), while OpenAI models remained competitive (9/20).
- Results continue to suggest model selection should be **task-specific** (e.g., detection narrative depth vs concise coding/triage output quality).

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
│   └── benchmark_analysis.ipynb
└── visualizations/
    ├── wins_by_model.png
    ├── wins_by_vendor.png
    └── winner_by_prompt.png
```


## Interactive Dashboard Features

The dashboard (`dashboard/index.html`) now includes:

- KPI cards for prompt count, vendor wins, model coverage, and top model ties
- Dual scoreboards (wins by vendor + top models by wins)
- Category chips, full-text search, and sortable prompt result rows
- Expand/collapse rationale details per prompt
- Model spotlight cards with win/loss/win-rate stats
- Head-to-head matchup summaries showing repeated pair outcomes

Open `dashboard/index.html` in a browser to explore the full interactive view.

## Prompt Set

The full prompt set is stored in `data/prompt_results.csv` (20 rows).

## Limitations

- Sample size is still modest relative to production benchmark suites.
- Pairwise testing means not every model was tested against every other model evenly.
- Judging was human-guided rather than automated with a strict numeric rubric.
- Prompt phrasing and chosen model matchups can affect outcomes.

## Why this project matters

For security teams, LLM adoption is not just about "best model overall." It is about **fit for purpose**:

- Which model explains ATT&CK techniques best?
- Which model gives the most realistic SOC workflow guidance?
- Which model is strongest at coding or analytics tasks?
- Which model behaves safely on hallucination tests?

This repo shows one lightweight way to evaluate those questions and iterate with more evidence over time.
