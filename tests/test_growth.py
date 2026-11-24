import concurrent.futures
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from channel_ops import growth


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "private" / "experiments.sqlite3"
        self.base = datetime.now(timezone.utc) - timedelta(days=20)
        growth.create_experiment("demo", "Two visitors convert at 50%", 2, 0.5, db_path=self.db)

    def event(self, event_id, kind, subject="", amount=0, day=0):
        return growth.record_event("demo", event_id, kind, subject, amount, self.db,
                                   occurred_at=(self.base + timedelta(days=day)).isoformat())

    def report(self):
        return growth.experiment_report("demo", self.db)

    def test_url_preserves_placement_and_replaces_duplicate_tags(self):
        result = growth.campaign_brief("pilot", "https://example.org/demo?x=2&UTM_source=x&utm_source=y#try",
                                       "newsletter", "referral", "Editors", "Show the receipts", "Weekly review", "Join pilot")
        url = urlsplit(result["url"])
        self.assertEqual(parse_qsl(url.query), [("x", "2"), ("utm_source", "newsletter"),
                                                ("utm_medium", "referral"), ("utm_campaign", "pilot")])
        self.assertEqual(url.fragment, "try")
        self.assertIn(result["url"], result["pitch_draft"])
        with self.assertRaises(ValueError):
            growth.campaign_brief("pilot", "https://user:pwd@example.org", "web", "pr", "a", "b", "c", "d")

    def test_hypothesis_immutable_and_retry_safe(self):
        growth.create_experiment("demo", "Two visitors convert at 50%", 2, 0.5, db_path=self.db)
        with self.assertRaises(ValueError):
            growth.create_experiment("demo", "Change success threshold", 2, 0.6, db_path=self.db)
        self.assertIsNone(self.report()["observed_rate"])

    def test_cohort_deduplication_maturity_and_money(self):
        self.event("e-a", "exposed", "a")
        self.event("e-a-again", "exposed", "a", day=1)
        self.event("paid-before", "paid", "a", 25, -1)
        self.assertEqual(self.report()["decision"], "collecting")
        self.event("e-b", "exposed", "b", day=1)
        self.event("e-c", "exposed", "c", day=2)
        self.event("sale-a", "paid", "a", 100, 3)
        self.event("sale-b", "paid", "b", 200, 8)  # exactly at the excluded deadline
        self.event("sale-c", "paid", "c", 300, 3)  # outside preregistered cohort
        self.event("refund-a", "refund", "a", 50, 4)
        self.event("fee", "expense", amount=40)
        report = self.report()
        self.assertEqual((report["enrolled"], report["matured"], report["converted"]), (2, 2, 1))
        self.assertEqual(report["decision"], "threshold_met")
        self.assertEqual(report["cash_ledger"]["net_after_recorded_costs_cents"], 535)

    def test_pending_and_failed_windows(self):
        growth.record_event("demo", "fresh-a", "exposed", "a", db_path=self.db)
        growth.record_event("demo", "fresh-b", "exposed", "b", db_path=self.db)
        self.assertEqual(self.report()["decision"], "awaiting_window")
        self.event("earlier-a", "exposed", "a")
        self.event("earlier-b", "exposed", "b")
        self.assertEqual(self.report()["decision"], "below_threshold")

    def test_cash_and_conversion_require_independent_evidence(self):
        self.event("a-sale", "paid", "a", 1000)
        self.assertEqual(self.report()["converted"], 0)
        self.assertEqual(self.report()["cash_ledger"]["receipts_cents"], 1000)
        with self.assertRaises(ValueError):
            self.event("lead-spend", "lead", "a", 42)
        with self.assertRaises(ValueError):
            self.event("email", "exposed", "person@example.org")
        with self.assertRaises(ValueError):
            self.event("tomorrow", "exposed", "a", day=21)

    def test_conflict_cross_campaign_and_atomic_import(self):
        self.event("evt-1", "lead", "a")
        self.assertFalse(self.event("evt-1", "lead", "a")["inserted"])
        growth.create_experiment("other", "A different campaign", 2, 0.5, db_path=self.db)
        with self.assertRaises(ValueError):
            growth.record_event("other", "evt-1", "lead", "a", 0, self.db)
        exported = growth.export_events("demo", self.db)
        with self.assertRaises(ValueError):
            growth.import_events("demo", [dict(exported[0], event_id="new"), dict(exported[0], subject="b")], self.db)
        self.assertEqual(growth.export_events("demo", self.db), exported)

    def test_export_import_roundtrip_and_concurrent_deliveries(self):
        def deliver(_):
            return growth.record_event("demo", "receipt-1", "paid", "p1", 1900, self.db)["inserted"]
        with concurrent.futures.ThreadPoolExecutor(6) as pool:
            self.assertEqual(sum(pool.map(deliver, range(12))), 1)
        other = Path(self.tmp.name) / "other.sqlite3"
        growth.create_experiment("demo", "Two visitors convert at 50%", 2, 0.5, db_path=other)
        exported = growth.export_events("demo", self.db)
        self.assertEqual(growth.import_events("demo", exported, other)["inserted"], 1)
        self.assertEqual(growth.import_events("demo", exported, other)["duplicates"], 1)
        self.assertEqual(growth.export_events("demo", other), exported)
        self.assertEqual(self.db.stat().st_mode & 0o077, 0)
