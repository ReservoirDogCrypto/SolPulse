"""Test suite for SolPulse. Standard library unittest; no network required.

    python3 -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solpulse import anomaly, demo, history, render_html, render_json, render_md
from solpulse.http import Result, SourceLog


class TestModifiedZ(unittest.TestCase):
    def test_needs_minimum_history(self):
        self.assertIsNone(anomaly._modified_z(100, [1, 2, 3]))

    def test_robust_to_historical_outlier(self):
        """A past spike must not mask a later genuine drop.

        This is the reason median/MAD is used instead of mean/stddev.
        """
        series = [3000, 3050, 2980, 3020, 3010, 2990, 3030, 15000]
        self.assertLess(abs(anomaly._modified_z(3000, series)), anomaly.Z_THRESHOLD)
        self.assertGreater(abs(anomaly._modified_z(800, series)), anomaly.Z_THRESHOLD)

    def test_constant_series_ignores_noise_but_catches_jumps(self):
        flat = [100] * 8
        self.assertEqual(anomaly._modified_z(100, flat), 0.0)
        self.assertEqual(anomaly._modified_z(102, flat), 0.0)      # within tolerance
        self.assertEqual(anomaly._modified_z(150, flat), anomaly.FLAT_SERIES_SCORE)
        self.assertEqual(anomaly._modified_z(50, flat), -anomaly.FLAT_SERIES_SCORE)

    def test_zero_median_does_not_divide_by_zero(self):
        self.assertIsInstance(anomaly._modified_z(5, [0] * 8), float)


class FakeHistory:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def series(self, metric, exclude_last=True):
        source = self.snapshots[:-1] if exclude_last and self.snapshots else self.snapshots
        return [s[metric] for s in source if isinstance(s.get(metric), (int, float))]


class TestAnomalyRules(unittest.TestCase):
    def test_healthy_network_is_quiet(self):
        result = anomaly.detect(
            {"health": "ok", "tps": 3000, "slot_time_ms": 410,
             "delinquent_stake_pct": 1.2, "nakamoto_coefficient": 22},
            FakeHistory([]))
        self.assertEqual(result["count"], 0)

    def test_unhealthy_node_is_critical(self):
        result = anomaly.detect({"health": "behind"}, FakeHistory([]))
        self.assertEqual(result["critical"], 1)

    def test_delinquent_stake_escalates(self):
        warn = anomaly.detect({"health": "ok", "delinquent_stake_pct": 7.0},
                              FakeHistory([]))
        crit = anomaly.detect({"health": "ok", "delinquent_stake_pct": 12.0},
                              FakeHistory([]))
        self.assertEqual(warn["warning"], 1)
        self.assertEqual(crit["critical"], 1)

    def test_rules_fire_without_any_history(self):
        """Absolute rules must work on the very first run."""
        result = anomaly.detect({"health": "ok", "tps": 100}, FakeHistory([]))
        self.assertGreaterEqual(result["critical"], 1)
        self.assertFalse(result["baseline_ready"])

    def test_nakamoto_at_real_world_level_is_quiet(self):
        """Solana's Nakamoto coefficient sits around 19.

        A threshold above that would fire on every run forever, which trains
        readers to ignore the whole panel. Degradation is the statistical
        layer's job; this rule only covers genuinely alarming levels.
        """
        quiet = anomaly.detect({"health": "ok", "nakamoto_coefficient": 19},
                               FakeHistory([]))
        alarming = anomaly.detect({"health": "ok", "nakamoto_coefficient": 14},
                                  FakeHistory([]))
        self.assertEqual(quiet["count"], 0)
        self.assertEqual(alarming["warning"], 1)

    def test_nakamoto_decline_caught_statistically(self):
        """A drop from the normal level still registers, via the baseline."""
        history_at_19 = FakeHistory([{"nakamoto_coefficient": 19}] * 8 + [{}])
        result = anomaly.detect({"health": "ok", "nakamoto_coefficient": 16},
                                history_at_19)
        self.assertGreaterEqual(result["count"], 1)

    def test_correlation_reported_when_domains_co_fire(self):
        result = anomaly.detect(
            {"health": "ok", "tps": 200, "delinquent_stake_pct": 12.0},
            FakeHistory([]))
        self.assertIsNotNone(result["correlation"])

    def test_no_correlation_for_single_domain(self):
        result = anomaly.detect({"health": "ok", "tps": 200}, FakeHistory([]))
        self.assertIsNone(result["correlation"])


class TestHistory(unittest.TestCase):
    def test_roundtrip_and_baseline_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            for i in range(7):
                hist = history.History(path)
                hist.append(f"2026-01-0{i + 1}T00:00:00", {"tps": 3000 + i})
                hist.save()
            self.assertEqual(len(history.History(path).snapshots), 7)

    def test_current_run_excluded_from_its_own_baseline(self):
        hist = FakeHistory([{"tps": 1}, {"tps": 2}, {"tps": 99}])
        self.assertEqual(hist.series("tps"), [1, 2])

    def test_corrupt_history_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            path.write_text("{not json")
            self.assertEqual(history.History(path).snapshots, [])

    def test_history_is_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = history.History(Path(tmp) / "h.json")
            for i in range(history.MAX_SNAPSHOTS + 60):
                hist.append(f"t{i}", {"tps": i})
            self.assertEqual(len(hist.snapshots), history.MAX_SNAPSHOTS)


class TestSourceLog(unittest.TestCase):
    def test_counts_reflect_failures(self):
        log = SourceLog()
        log.record(Result(ok=True, source="a"))
        log.record(Result.failure("b", "HTTP 500"))
        self.assertEqual((log.healthy, log.total), (1, 2))


class TestFormatting(unittest.TestCase):
    def test_magnitudes(self):
        self.assertEqual(render_html.fmt(1_500_000_000, "$"), "$1.50B")
        self.assertEqual(render_html.fmt(2_400_000, "$"), "$2.4M")
        self.assertEqual(render_html.fmt(None), "—")

    def test_identifiers_are_never_abbreviated(self):
        self.assertEqual(render_html.fmt_exact(298_459_000), "298,459,000")

    def test_escaping_blocks_injection(self):
        self.assertNotIn("<script>", render_html.esc("<script>alert(1)</script>"))


class TestRenderers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        log = demo.build_log()
        cls.report = {
            "version": "test",
            "generated_at": "2026-08-18 00:00:00 UTC",
            "metrics": demo.build_metrics(),
            "anomalies": anomaly.detect(demo.build_metrics(), FakeHistory([])),
            "sources": {"healthy": log.healthy, "total": log.total,
                        "entries": log.entries},
        }

    def test_json_is_valid_and_grouped(self):
        parsed = json.loads(render_json.render(self.report))
        self.assertEqual(parsed["schema_version"], render_json.SCHEMA_VERSION)
        for group in ("network", "validators", "economics", "supply"):
            self.assertIn(group, parsed["metrics"])
        self.assertEqual(len(parsed["timeseries"]["tps_samples"]), 60)

    def test_markdown_has_all_sections(self):
        text = render_md.render(self.report)
        for heading in ("# Solana Ecosystem Report", "## Network performance",
                        "## Validators", "## Economics", "## Source status"):
            self.assertIn(heading, text)

    def test_html_is_self_contained(self):
        page = render_html.render(self.report)
        self.assertTrue(page.startswith("<!doctype html>"))
        # No external requests of any kind: the CSP-free promise of the report.
        for marker in ("http://", "cdn.", "<link", "src=\"http"):
            self.assertNotIn(marker, page)
        self.assertIn("data-points", page)      # hover layer wired
        self.assertIn("View as table", page)    # accessible alternative present

    def test_html_survives_missing_metrics(self):
        sparse = dict(self.report, metrics={"health": "ok"})
        page = render_html.render(sparse)
        self.assertIn("<!doctype html>", page)
        self.assertIn("—", page)  # placeholders, not crashes


class TestOutputs(unittest.TestCase):
    def test_html_written_as_index_for_pages(self):
        """GitHub Pages serves index.html at the root.

        Without it the published dashboard is a 404, which silently costs the
        live-demo the whole point of being hosted.
        """
        # solpulse.py (entry script) and solpulse/ (package) share a name, so
        # a plain import resolves to the package. Load the script by path.
        import importlib.util

        script = Path(__file__).resolve().parent.parent / "solpulse.py"
        spec = importlib.util.spec_from_file_location("solpulse_cli", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        with tempfile.TemporaryDirectory() as tmp:
            report = {
                "version": "test",
                "generated_at": "2026-08-22 00:00:00 UTC",
                "metrics": demo.build_metrics(),
                "deltas": {},
                "anomalies": anomaly.detect(demo.build_metrics(), FakeHistory([])),
                "sources": {"healthy": 1, "total": 1, "entries": []},
            }
            written = cli.write_outputs(report, Path(tmp), ["html"])
            names = {p.name for p in written}
            self.assertIn("index.html", names)
            self.assertIn("dashboard.html", names)

    def test_deltas_render_when_present(self):
        report = {
            "version": "test", "generated_at": "t",
            "metrics": demo.build_metrics(),
            "deltas": {"tps": 7.8},
            "anomalies": anomaly.detect(demo.build_metrics(), FakeHistory([])),
            "sources": {"healthy": 1, "total": 1, "entries": []},
        }
        page = render_html.render(report)
        self.assertIn("vs last run", page)
        self.assertIn("7.8%", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
