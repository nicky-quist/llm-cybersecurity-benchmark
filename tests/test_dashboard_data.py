"""
Regression tests for the dashboard's embedded data and the collection harness.

The defect these exist to prevent: dashboard/index.html used to carry its own
hand-pasted copy of the twenty comparisons. It had already drifted — the
categories in the page had been title-cased into "Soc Detection" and
"Ai For Cybersecurity", which match nothing in data/prompt_results.csv — and a
hand-maintained second copy is the same failure mode that once dropped GPT-4o,
the only model with a significant result, out of the reported tables entirely.

The page now carries a generated block, analysis/build_dashboard.py is the only
thing allowed to write it, and these tests fail if the two drift apart again.
"""
import csv
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import build_dashboard
from harness import schedule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(ROOT, "dashboard", "index.html")
RESULTS = os.path.join(ROOT, "data", "prompt_results.csv")


def read_dashboard():
    with open(DASHBOARD, encoding="utf-8") as f:
        return f.read()


def embedded(name):
    """Pull one of the generated JS arrays back out of the page."""
    html = read_dashboard()
    match = re.search(rf"const {name} = (\[.*?\]);\n", html, re.S)
    if not match:
        raise AssertionError(f"no generated `const {name}` block in dashboard/index.html")
    return json.loads(match.group(1))


class TestDashboardIsInSyncWithSource(unittest.TestCase):
    def test_generated_block_matches_the_csvs(self):
        models = build_dashboard.load_models()
        comparisons = build_dashboard.load_comparisons()
        expected = build_dashboard.splice(read_dashboard(),
                                          build_dashboard.render_block(models, comparisons))
        self.assertEqual(
            expected, read_dashboard(),
            "dashboard/index.html is stale — run: python analysis/build_dashboard.py")

    def test_every_comparison_reaches_the_page(self):
        with open(RESULTS, encoding="utf-8-sig") as f:
            source = list(csv.DictReader(f))
        self.assertEqual(len(embedded("COMPARISONS")), len(source))

    def test_categories_are_not_mangled(self):
        """The old page title-cased categories, so "SOC detection" became "Soc Detection"."""
        with open(RESULTS, encoding="utf-8-sig") as f:
            source = {r["category"] for r in csv.DictReader(f)}
        self.assertEqual({r["category"] for r in embedded("COMPARISONS")}, source)


class TestVendorsComeFromTheRegistry(unittest.TestCase):
    """Vendor used to be inferred as `startsWith("Gemini") ? Google : OpenAI`.

    That is not merely fragile — it silently mislabels every model from any
    third vendor as OpenAI, which is precisely the change being made now.
    """

    def test_every_compared_model_is_registered(self):
        models = {m["model"] for m in build_dashboard.load_models()}
        appearing = {m for r in build_dashboard.load_comparisons()
                     for m in (r["model_a"], r["model_b"])}
        self.assertEqual(appearing - models, set(),
                         "models appear in comparisons but not in data/models.csv, "
                         "so the dashboard would render their vendor as Unknown")

    def test_no_model_name_prefix_is_relied_on(self):
        html = read_dashboard()
        self.assertNotIn('startsWith("Gemini")', html,
                         "vendor must come from data/models.csv, not from the model name")

    def test_every_vendor_has_brand_colours(self):
        html = read_dashboard()
        for vendor in {m["vendor"] for m in build_dashboard.load_models()}:
            for suffix in ("", "-2", "-soft"):
                self.assertIn(f"--v-{vendor}{suffix}:", html,
                              f"vendor {vendor} has no --v-{vendor}{suffix} colour defined, "
                              f"so its charts and chips would fall back to grey")

    def test_status_column_matches_the_comparison_data(self):
        """A vendor with no comparisons must be marked planned, not evaluated."""
        build_dashboard.validate(build_dashboard.load_models(),
                                 build_dashboard.load_comparisons())


class TestScheduleIsPowered(unittest.TestCase):
    """The current dataset's real problem is the schedule, not the models.

    Six of eight models were drawn so few times that no record they could have
    produced would reach p <= 0.05. A generated schedule has to do better than
    that or it is not worth running.
    """

    def test_every_model_can_produce_a_significant_result(self):
        models = schedule.load_models()
        plan = schedule.build(models, schedule.load_prompts(), repeats=1, target=6)

        appearances = {}
        for row in plan:
            for m in (row["model_a"], row["model_b"]):
                appearances[m] = appearances.get(m, 0) + 1

        self.assertEqual(set(appearances), {m["model"] for m in models},
                         "some registered model is never scheduled")

        for model, n in appearances.items():
            best_p = 2 * (0.5 ** n)
            self.assertLessEqual(
                best_p, 0.05,
                f"{model} is scheduled {n} times; even a perfect {n}-0 record gives "
                f"p = {best_p:.3f}, so no outcome it produces could be significant")

    def test_committed_pairings_file_is_still_valid(self):
        path = os.path.join(ROOT, "harness", "pairings.csv")
        if not os.path.exists(path):
            self.skipTest("no committed schedule")
        registered = {m["model"] for m in schedule.load_models()}
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row["model_a"], registered)
            self.assertIn(row["model_b"], registered)
            self.assertNotEqual(row["model_a"], row["model_b"],
                                "a model is scheduled against itself")


if __name__ == "__main__":
    unittest.main()
