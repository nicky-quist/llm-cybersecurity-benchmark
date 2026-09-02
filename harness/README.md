# Collection harness

The first twenty comparisons were run by hand in Handshake AI Versus. That platform
is no longer reachable, and while its judging was blind — model names withheld until
the verdict was in — the original method had three limitations that a manual workflow
could not fix anyway:

- raw model outputs were never archived, so no judgement can be independently re-scored
- only a winner and a one-line note were recorded — no rubric, and no record of which
  response was shown first, so position bias can't be tested
- pairings were drawn ad hoc, leaving six of eight models unable to produce a
  significant result no matter how they performed

This harness replaces the platform and fixes all three.

```
schedule.py  ->  a balanced pairing plan, computed before any response is read
collect.py   ->  calls each vendor's API and archives every raw response to disk
judge.py     ->  presents the two responses blind, records the verdict and a rubric
```

Everything is stdlib Python — no dependencies, same as `analysis/`.

## The plan it produces

`harness/pairings.csv` is the committed schedule: **33 comparisons, 11 models,
every model appearing exactly 6 times, 82% of them cross-vendor.**

Six appearances is not arbitrary. It is the smallest number at which a perfect
record reaches p ≤ 0.05 under an exact binomial test — at five appearances, a
model that wins every single comparison still lands at p = 0.06. Six of the eight
models in the current dataset were below that line, which means their results were
unfalsifiable before the first response was read. Regenerate with different
parameters if you want:

```bash
python harness/schedule.py --repeats 1 --target 6 --out harness/pairings.csv
```

`--summary` prints the appearances and best achievable p-value per model without
writing anything, which is the check worth running before spending money on a round.

### Making per-category claims possible

The default schedule balances **models**, not **categories** — and the project's
actual research question is about categories: *do different models suit different
SOC task types?* Round one had twenty prompts across twenty categories, one
observation each, which cannot answer that at any level of care.

```bash
python harness/schedule.py --repeats 1 --per-category 3 --out harness/pairings.csv
```

That produces **60 comparisons with exactly 3 per category**, every model at 9–10
appearances and 82% cross-vendor. Three per category is still thin, but it is the
difference between a hypothesis and a measurement. `--summary` names every category
that falls short.

## Running a round

### 1. Collect responses

```bash
python harness/collect.py --dry-run
```

Set whichever API keys you have — the script skips vendors whose key is absent
rather than failing, so you can collect one vendor at a time:

```bash
$env:ANTHROPIC_API_KEY = "..."      # PowerShell
$env:OPENAI_API_KEY    = "..."
$env:GOOGLE_API_KEY    = "..."

python harness/collect.py --models Claude-Opus-5,Claude-Sonnet-5,Claude-Haiku-4.5
```

Each response lands in `responses/<prompt_id>/<model>.md` with the model id, token
limit and collection timestamp in its front matter. Already-archived responses are
skipped, so the script is safe to re-run after a failure. Check the model ids in
`API_IDS` at the top of `collect.py` against each provider's current model list
first — providers rename and retire ids, and a stale one fails with an unhelpful 404.

A full round is 66 responses at ~2k output tokens each. That is a small bill at
current API prices, but check the provider pricing pages rather than trusting a
number written down here.

### 2. Judge them blind, in the browser

```bash
python harness/judge.py --render
```

That writes `harness/blind/index.html` plus one page per comparison. Open the index
and work through them: the two responses sit side by side as **Response A** and
**Response B** with the model names withheld, in an order fixed by a seed rather
than by the schedule. Under each pair are the verdict buttons, a 1–5 scale for each
of the five rubric dimensions — correctness, completeness, usefulness, clarity,
grounding — and a one-line box for what decided it.

Verdicts are held in that browser's `localStorage`, so you can stop and come back.
When you're done, click **Export verdicts**, save the JSON, and hand it back:

```bash
python harness/judge.py --import harness/verdicts.json --append
```

The page records only `"a"` or `"b"`. Resolving that to a model name happens in
`judge.py`, using the same seed that decided the presentation order — which is what
makes the blinding real rather than cosmetic. There is nothing in the delivered HTML
for a curious judge to inspect.

`--append` also writes the verdict into `data/prompt_results.csv` as round 2.

Prefer a terminal? `python harness/judge.py` still runs the same flow interactively,
and both paths write through the same code so they cannot drift.

### 3. Check the judging before you trust it

```bash
python analysis/agreement.py
```

Three checks on the judge, not the models:

- **Cohen's kappa** between each pair of judges on the pairings they both scored,
  reported next to raw agreement — because kappa alone misleads when the marginals
  are skewed (90% agreement can produce a kappa near zero). Needs a second rater:
  have them run `python harness/judge.py --judge <their-name>` on the same pairings.
- **Position bias** — how often the judge picked whichever response was shown as A.
  `judge.py` assigns A/B from a seed, so a fair process sits near 50%. A significant
  departure means verdicts are tracking layout rather than content, which blinding
  does not fix.
- **Rubric consistency** — how often the declared winner also had the higher rubric
  total. Overrides are legitimate; a high rate means the rubric is not measuring
  what the verdicts are actually being decided on.

### 4. Regenerate everything downstream

```bash
python analysis/statistics.py --write
python analysis/build_dashboard.py
python -m unittest discover -s tests -t .
```

The dashboard picks up the third vendor on its own. With three vendors carrying
data, the vendor-level test switches from an exact binomial to a chi-square
goodness of fit, because the two-group exact test no longer applies.

## Known confounds in the round-two archive

Recorded here rather than discovered later by someone reading the CSV.

- **Mixed collection methods.** Responses carry `collected_via` in their front
  matter: `api` (clean, via `collect.py`), `manual-paste` (from a chat UI or
  LMArena), or `claude-code-session`. These are not equivalent — chat interfaces
  apply their own system prompts and do not expose sampling parameters. Any
  comparison across two different `collected_via` values carries that confound.
- **Asymmetric formatting repair.** LMArena's side-by-side view strips Markdown
  on copy. Those responses had their structure (headings, lists, tables)
  reconstructed during archiving; responses that arrived already-formatted did
  not. The reconstruction changed presentation, not content, but it was applied
  to one side of several pairings and not the other. The blind judging page runs
  both responses through the *same* renderer, which limits the effect to whatever
  the reconstruction got wrong.
- **Model substitution.** Where the served model differed from the scheduled one
  (LMArena serving Gemini-2.5-Flash for a slot scheduled as Gemini-2.5-Pro), the
  archive records the model that actually ran. The scheduled pairing stays open.
- **Pairings marked `as-served`** in `pairings.csv` were not planned in advance —
  they are the pairs LMArena happened to show together. They are legitimate
  comparisons but they are not part of the balanced design, and they reintroduce
  exactly the ad-hoc-draw problem the schedule exists to avoid. Filter on
  `tier == "as-served"` to exclude them from a balanced analysis.

## Why a human still judges

It would be easy to have a model score these comparisons automatically, and for a
project whose entire argument is about reporting what the data supports, it would
be the wrong call. A model judging a comparison that contains its own output is
self-preference bias — a well-documented and large effect. A model judging its
competitors' output is not neutral either.

If you do want an automated judge, it belongs **alongside** human scoring, not in
place of it, with the agreement rate between the two reported as a number. That is
a real experiment. Silently swapping the judge is not.

## No API keys?

[LMArena](https://lmarena.ai) is the closest free replacement for Handshake Versus:
side-by-side model responses, pick a winner, no key required. Its Direct Chat mode
lets you choose specific models rather than taking a random draw.

Working that way, `harness/pairings.csv` is still the schedule to follow, and you
still paste both responses into `responses/<prompt_id>/<model>.md` so the archive
gap gets closed. `judge.py` will pick them up from there like any other round.
