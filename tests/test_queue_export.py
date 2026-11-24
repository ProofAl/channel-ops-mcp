import csv
import io
import unittest

from channel_ops.queue_export import COLUMNS, export_queue_draft


class QueueExportTests(unittest.TestCase):
    def setUp(self):
        self.draft = dict(content_id="weekly-clip-01", title='Съёмка, дубль "два"',
                          description="Строка 1\r\n- Второй пункт", target_id="studio-test",
                          media_ref="clip-v2.mp4", evidence_ref="#123")

    def test_exact_columns_quotes_and_outcome_fields(self):
        output = export_queue_draft(**self.draft)
        reader = csv.DictReader(io.StringIO(output, newline=""))
        self.assertEqual(reader.fieldnames, list(COLUMNS))
        row, = list(reader)
        self.assertEqual(row["text"], self.draft["title"] + "\nСтрока 1\n- Второй пункт")
        self.assertEqual((row["channel"], row["status"], row["visibility"], row["origin"]),
                         ("youtube", "draft", "private", "control"))
        self.assertTrue(all(row[k] == "" for k in ("scheduled_at", "published_at", "remote_post_id", "last_error")))
        self.assertEqual(output, export_queue_draft(**self.draft))

    def test_shorts_video_references_and_click_tracking(self):
        url = "https://example.org/demo?content=1&utm_source=old"
        output = export_queue_draft(**self.draft, channel="youtube_shorts", link_url=url,
                                    utm_campaign="pilot")
        row, = csv.DictReader(io.StringIO(output))
        self.assertEqual((row["channel"], row["link_url"], row["utm_campaign"]),
                         ("youtube_shorts", url, "pilot"))
        self.assertEqual(row["evidence_ref"], "#123")

    def test_injection_control_characters_and_target_confusion(self):
        for changes in (
            {"title": " \t=1+1"}, {"title": "＠SUM(A1)"}, {"title": "a\rnew title"},
            {"pillar": "+1"}, {"utm_campaign": "  -1"}, {"content_id": "=SUM(1)"},
            {"link_url": "https://example.org/\n=1"}, {"link_url": "http://example.org"},
            {"link_url": "https://user:secret@example.org"}, {"channel": "x"},
            {"target_id": ""}, {"target_id": "a/b"}, {"media_ref": "../video.mp4"},
            {"evidence_ref": ""}, {"title": " "}, {"title": "a" * 101},
            {"description": "я" * 2501}, {"link_url": "https://example.org/", "description": "x" * 4999},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                export_queue_draft(**(self.draft | changes))
