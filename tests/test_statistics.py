"""
Regression tests for the reporting pipeline.

The defect these exist to prevent: `data/model_wins.csv` was maintained by hand
and listed only models with at least one win, so GPT-4o — which lost all six of
its comparisons, and is the only model in this dataset whose result is
statistically distinguishable from chance — was absent from the results table,
the README, and the dashboard chart. A model that loses everything is not a
missing row; it is the finding.
"""
import csv
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.statistics import (binomial_two_sided_p, bradley_terry,
                                 build_vendor_lookup, load_results, tally,
                                 vendor_split, wilson_interval)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_WINS = os.path.join(ROOT, "data", "model_wins.csv")


class TestEveryModelIsReported(unittest.TestCase):
    def test_no_model_is_dropped_from_the_derived_table(self):
        rows = load_results()
        appearing = {m for r in rows for m in (r["model_a"], r["model_b"])}
        with open(MODEL_WINS, encoding="utf-8") as f:
            reported = {row["model"] for row in csv.DictReader(f)}
        missing = appearing - reported
        self.assertEqual(missing, set(),
                         f"models appear in comparisons but not in model_wins.csv: "
                         f"{sorted(missing)} — this is exactly how GPT-4o vanished")

    def test_winless_models_are_still_reported(self):
        rows = load_results()
        stats = tally(rows)
        winless = {m for m, s in stats.items() if s["wins"] == 0}
        with open(MODEL_WINS, encoding="utf-8") as f:
            reported = {row["model"] for row in csv.DictReader(f)}
        for model in winless:
            self.assertIn(model, reported,
                          f"{model} has zero wins and was omitted from the report")

    def test_derived_table_carries_appearances(self):
        """A win count without an appearance count is not interpretable."""
        with open(MODEL_WINS, encoding="utf-8") as f:
            header = next(csv.reader(f))
        for column in ("appearances", "wins", "losses", "win_rate", "ci_low", "ci_high"):
            self.assertIn(column, header)

    def test_derived_table_matches_source(self):
        rows = load_results()
        stats = tally(rows)
        with open(MODEL_WINS, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                s = stats[row["model"]]
                self.assertEqual(int(row["wins"]), s["wins"])
                self.assertEqual(int(row["appearances"]), s["appearances"])
                self.assertEqual(int(row["losses"]), s["losses"])


class TestSourceDataIntegrity(unittest.TestCase):
    def test_winner_is_always_one_of_the_two_models(self):
        load_results()  # raises if not

    def test_loser_column_agrees_with_the_pairing(self):
        for r in load_results():
            expected = r["model_b"] if r["winner"] == r["model_a"] else r["model_a"]
            self.assertEqual(r["loser"], expected,
                             f"prompt {r['prompt_id']}: loser column disagrees with the pairing")

    def test_vendor_matches_the_registry(self):
        """winner_vendor must agree with data/models.csv, not with a name prefix.

        This test used to read `"Google" if winner.startswith("Gemini") else
        "OpenAI"`, which is the same heuristic the dashboard used and has the same
        defect: it assigns every model from any third vendor to OpenAI. It began
        failing the moment a Claude model won a comparison — correctly, because
        the assertion was wrong, not the data.
        """
        rows = load_results()
        vendor_of = build_vendor_lookup(rows)
        for r in rows:
            self.assertEqual(
                r["winner_vendor"], vendor_of(r["winner"]),
                f"prompt {r['prompt_id']}: winner_vendor disagrees with data/models.csv")

    def test_every_model_is_registered(self):
        rows = load_results()
        vendor_of = build_vendor_lookup(rows)
        for r in rows:
            for field in ("model_a", "model_b"):
                self.assertNotEqual(
                    vendor_of(r[field]), "Unknown",
                    f"prompt {r['prompt_id']}: {r[field]} is missing from data/models.csv")

    def test_wins_and_losses_balance(self):
        stats = tally(load_results())
        self.assertEqual(sum(s["wins"] for s in stats.values()), len(load_results()))
        self.assertEqual(sum(s["losses"] for s in stats.values()), len(load_results()))


class TestStatistics(unittest.TestCase):
    def test_wilson_interval_is_non_degenerate_at_zero_wins(self):
        """The normal approximation gives a zero-width interval at 0/6, which is
        precisely where GPT-4o sits."""
        lo, hi = wilson_interval(0, 6)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.2)

    def test_wilson_interval_contains_the_point_estimate(self):
        for wins, n in ((0, 6), (2, 3), (4, 7), (11, 20), (5, 5)):
            lo, hi = wilson_interval(wins, n)
            self.assertLessEqual(lo, wins / n)
            self.assertGreaterEqual(hi, wins / n)

    def test_wilson_narrows_as_n_grows(self):
        narrow = wilson_interval(50, 100)
        wide = wilson_interval(5, 10)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])

    def test_binomial_test_against_known_values(self):
        self.assertAlmostEqual(binomial_two_sided_p(10, 20), 1.0, places=6)
        self.assertLess(binomial_two_sided_p(20, 20), 1e-5)
        self.assertGreater(binomial_two_sided_p(11, 20), 0.5)

    def test_the_vendor_split_is_not_significant(self):
        """If this ever fails, the claim in the README needs revisiting — which is
        the point of asserting it rather than writing it down once."""
        counts = vendor_split(load_results())
        total = sum(counts.values())
        top = counts.most_common(1)[0][1]
        self.assertGreater(binomial_two_sided_p(top, total), 0.05,
                           "the vendor split is now significant; update the README")

    def test_bradley_terry_is_defined_for_a_winless_model(self):
        """Without a prior the MLE strength of a 0-win model is zero and the fit
        does not converge."""
        strengths = bradley_terry(load_results())
        for model, s in strengths.items():
            self.assertGreater(s, 0.0, f"{model} has non-positive strength")
            self.assertTrue(math.isfinite(s))

    def test_bradley_terry_ranks_the_winless_model_last(self):
        strengths = bradley_terry(load_results())
        stats = tally(load_results())
        winless = [m for m, s in stats.items() if s["wins"] == 0]
        for model in winless:
            self.assertEqual(model, min(strengths, key=strengths.get))

    def test_bradley_terry_covers_every_model(self):
        rows = load_results()
        appearing = {m for r in rows for m in (r["model_a"], r["model_b"])}
        self.assertEqual(set(bradley_terry(rows)), appearing)


if __name__ == "__main__":
    unittest.main()
