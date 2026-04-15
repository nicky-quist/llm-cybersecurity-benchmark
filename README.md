# LLM Evaluation for Cybersecurity SOC Tasks

A small benchmarking project comparing different large language models on cybersecurity and SOC-oriented tasks using **Handshake AI Versus** pairwise comparisons.

## Project Goal

This project evaluates how different LLMs perform on technical tasks that matter in a SOC or security engineering workflow, including:

- MITRE ATT&CK explanation
- SOC detection guidance
- incident investigation
- Splunk detection engineering
- Python scripting
- threat intelligence concepts
- anomaly detection for cyber
- reasoning and planning
- hallucination resistance
- AI-in-SOC strategic analysis

Rather than claiming broad model superiority, this project explores whether **different models perform better on different cybersecurity task types**.

## Methodology

- Platform: Handshake AI Versus
- Evaluation design: pairwise model comparisons
- Number of prompts: 10
- Domains tested:
  - cybersecurity knowledge
  - SOC detection and IR
  - detection engineering
  - coding
  - reasoning
  - hallucination handling
  - AI for cyber operations

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
| Gemini-2.5-Flash-Lite | 2 |
| Gemini-3.1-Pro-Preview | 2 |
| GPT-4.1-Mini | 2 |
| Gemini-3-Flash-Preview | 1 |
| Gemini-2.5-Pro | 1 |
| GPT-5.2 | 1 |
| GPT-5.2-High | 1 |

### Wins by vendor

| Vendor | Wins |
|---|---:|
| Google | 6 |
| OpenAI | 4 |

### Key takeaways

- No single model dominated every category.
- **Gemini-3.1-Pro-Preview** and **GPT-4.1-Mini** tied for the highest number of wins in this test set.
- Google models performed especially well on **SOC explanation, detection guidance, and strategic cyber reasoning** tasks.
- OpenAI models performed especially well on **Python scripting, anomaly detection framing, hallucination handling, and logic/math correctness** in this sample.
- The results suggest that model choice may depend on the task:
  - deeper cyber narrative and detection guidance vs.
  - concise correctness, coding robustness, and refusal behavior.

## Repository Structure

```text
llm-cybersecurity-benchmark/
├── README.md
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

## Prompt Set

The exact prompts used are stored in `data/prompt_results.csv`.

Prompt categories included:

1. MITRE ATT&CK T1059 explanation
2. SOC detection methods for T1059
3. Phishing-to-PowerShell incident investigation
4. Splunk query for suspicious PowerShell
5. Python brute-force detection script
6. IOC vs TTP explanation
7. Anomaly detection in network traffic
8. SOC staffing math
9. Hallucination test with a nonexistent incident
10. AI advantages and risks in SOC operations

## Limitations

- Small sample size: only {len(df)} prompts.
- Pairwise testing means not every model was tested against every other model.
- Judging was human-guided rather than automated with a strict numeric rubric.
- Prompt phrasing and the chosen model matchups can affect outcomes.

## Why this project matters

For security teams, LLM adoption is not just about "best model overall." It is about **fit for purpose**:

- Which model explains ATT&CK techniques best?
- Which model gives the most realistic SOC workflow guidance?
- Which model is strongest at coding or analytics tasks?
- Which model behaves safely on hallucination tests?

This repo shows one lightweight way to evaluate those questions.

