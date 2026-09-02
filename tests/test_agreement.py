"""
Tests for judge-reliability statistics and category coverage in the schedule.

These cover the two limitations round one could not address at all: there was no
second rater, so no agreement figure existed, and every category had exactly one
comparison, so no per-category claim was supportable. Both are now measurable —
these tests check the measurements are right before anyone relies on them.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.agreement import (binomial_two_sided_p, canonical_rating,
                                cohen_kappa, interpret)
from harness import schedule


class TestCohenKappa(unittest.TestCase):
    def test_worked_example(self):
        """8/10 agreement with even marginals is kappa = 0.6, not 0.8."""
        a = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        b = [1, 1, 1, 1, 0, 1, 0, 0, 0, 0]
        kappa, po, n = cohen_kappa(list(zip(a, b)))
        self.assertEqual(n, 10)
        self.assertAlmostEqual(po, 0.8)
        self.assertAlmostEqual(kappa, 0.6)

    def test_perfect_agreement_with_variation(self):
        pairs = [(1, 1), (0, 0), (1, 1), (0, 0)]
        kappa, po, _ = cohen_kappa(pairs)
        self.assertAlmostEqual(po, 1.0)
        self.assertAlmostEqual(kappa, 1.0)

    def test_no_marginal_variation_is_undefined_not_perfect(self):
        """Both judges picking the same label every time.

        Raw agreement is 100% and kappa is undefined. Reporting 1.0 would claim
        the judges demonstrated reliability when chance alone explains all of it.
        """
        kappa, po, _ = cohen_kappa([(1, 1)] * 8)
        self.assertIsNone(kappa)
        self.assertAlmostEqual(po, 1.0)

    def test_chance_level_agreement_is_near_zero(self):
        pairs = [(1, 1), (1, 0), (0, 1), (0, 0)]
        kappa, po, _ = cohen_kappa(pairs)
        self.assertAlmostEqual(po, 0.5)
        self.assertAlmostEqual(kappa, 0.0)

    def test_empty_input(self):
        self.assertEqual(cohen_kappa([]), (None, None, 0))

    def test_interpretation_bands(self):
        self.assertEqual(interpret(None), "undefined")
        self.assertEqual(interpret(0.9), "almost perfect")
        self.assertEqual(interpret(0.5), "moderate")
        self.assertEqual(interpret(-0.2), "worse than chance")


class TestCanonicalRating(unittest.TestCase):
    """A verdict is 'X beat Y', and X changes between rows.

    Kappa needs a label that means the same thing on every item, so the verdict
    is re-encoded as 'did the alphabetically-first model win?'.
    """

    def test_same_verdict_encodes_identically_whichever_side_won(self):
        row_a = {"winner": "Claude-Opus-5", "loser": "GPT-5.2"}
        row_b = {"winner": "GPT-5.2", "loser": "Claude-Opus-5"}
        self.assertEqual(canonical_rating(row_a), 1)   # Claude sorts first
        self.assertEqual(canonical_rating(row_b), 0)

    def test_two_judges_agreeing_produce_equal_ratings(self):
        judge_1 = {"winner": "GPT-4o", "loser": "Gemini-2.5-Pro"}
        judge_2 = {"winner": "GPT-4o", "loser": "Gemini-2.5-Pro"}
        self.assertEqual(canonical_rating(judge_1), canonical_rating(judge_2))


class TestPositionBiasTest(unittest.TestCase):
    def test_even_split_is_not_significant(self):
        self.assertGreater(binomial_two_sided_p(10, 20), 0.05)

    def test_strong_skew_is_significant(self):
        self.assertLess(binomial_two_sided_p(18, 20), 0.05)

    def test_matches_known_value(self):
        """11-9 is the round-one vendor split; p = 0.82."""
        self.assertAlmostEqual(binomial_two_sided_p(11, 20), 0.8238, places=3)


class TestCategoryCoverage(unittest.TestCase):
    def test_default_schedule_leaves_categories_thin(self):
        """Documents the limitation rather than pretending it is solved.

        The default schedule balances models, not categories. Per-category claims
        need --per-category, and this test fails loudly if that stops being true.
        """
        plan = schedule.build(schedule.load_models(), schedule.load_prompts(),
                              repeats=1, target=6, per_category=1)
        counts = {}
        for row in plan:
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        self.assertLess(min(counts.values()), 3)

    def test_per_category_three_is_honoured(self):
        plan = schedule.build(schedule.load_models(), schedule.load_prompts(),
                              repeats=1, target=6, per_category=3)
        counts = {}
        for row in plan:
            counts[row["category"]] = counts.get(row["category"], 0) + 1

        categories = {p["category"] for p in schedule.load_prompts()}
        self.assertEqual(set(counts), categories, "a category was dropped entirely")
        for category, n in counts.items():
            self.assertGreaterEqual(n, 3, f"{category} only has {n} comparisons")

    def test_category_topup_does_not_unbalance_the_models(self):
        """Filling thin categories must not undo the appearance balancing."""
        plan = schedule.build(schedule.load_models(), schedule.load_prompts(),
                              repeats=1, target=6, per_category=3)
        appearances = {}
        for row in plan:
            for m in (row["model_a"], row["model_b"]):
                appearances[m] = appearances.get(m, 0) + 1

        for model, n in appearances.items():
            best_p = 2 * (0.5 ** n)
            self.assertLessEqual(best_p, 0.05,
                                 f"{model} scheduled {n} times — no record could be significant")
        spread = max(appearances.values()) - min(appearances.values())
        self.assertLessEqual(spread, 3, f"appearances range too wide: {appearances}")

    def test_no_model_is_scheduled_against_itself(self):
        plan = schedule.build(schedule.load_models(), schedule.load_prompts(),
                              repeats=1, target=6, per_category=3)
        for row in plan:
            self.assertNotEqual(row["model_a"], row["model_b"])


if __name__ == "__main__":
    unittest.main()
