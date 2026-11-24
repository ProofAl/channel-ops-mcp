import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from channel_ops import youtube as yt


CHANNEL = "UC" + "a" * 22
VIDEO = "123456789ab"
ITEM = {"id": VIDEO, "etag": "v1", "snippet": {
    "categoryId": "27", "channelId": CHANNEL, "title": "Old", "description": "Keep",
    "tags": ["tag"], "defaultLanguage": "ru", "publishedAt": "2026-01-01",
}}


class YouTubeTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.folder = Path(folder)
        self.enterContext(patch.object(yt, "_home", return_value=self.folder))
        self.owner = yt._Owner(CHANNEL, "test-token")
        self.enterContext(patch.object(yt, "_owner", return_value=self.owner))
        self.request = self.enterContext(patch.object(yt, "_request"))
        self.title = "Old"

        def fake(method, url, **options):
            if url == yt.API + "channels":
                return {"items": [{"id": CHANNEL, "snippet": {"title": "Demo"}, "statistics": {},
                                   "contentDetails": {"relatedPlaylists": {"uploads": "test-uploads"}}}]}
            if url == yt.API + "playlistItems":
                return {"items": [{"contentDetails": {"videoId": VIDEO}, "snippet": {"title": self.title}}]}
            if url == yt.REPORTS:
                return {"columnHeaders": [{"name": "day"}, {"name": "views"}], "rows": []}
            if url == yt.API + "videos":
                if method == "GET":
                    return {"items": [{**ITEM, "snippet": {**ITEM["snippet"], "title": self.title}}]}
                if method == "PUT":
                    self.title = options["json"]["snippet"]["title"]
                    return {"id": VIDEO}
            raise AssertionError((method, url))

        self.request.side_effect = fake

    def draft(self):
        return yt.propose_title(VIDEO, "Новый заголовок")["proposal_id"]

    def test_verified_title_preserves_other_mutable_fields(self):
        pid = self.draft()
        self.assertTrue(all(c.args[0] == "GET" for c in self.request.call_args_list))
        result = yt._apply_title(pid, lambda d: True)
        self.assertTrue(result["verified"])
        put = next(c for c in self.request.call_args_list if c.args[0] == "PUT")
        expected = {"categoryId": "27", "description": "Keep", "tags": ["tag"],
                    "defaultLanguage": "ru", "title": "Новый заголовок"}
        self.assertEqual(put.kwargs["json"], {"id": VIDEO, "snippet": expected})
        self.assertEqual(put.kwargs["params"], {"part": "snippet"})
        self.assertEqual(put.kwargs["headers"]["If-Match"], '"v1"')
        with self.assertRaisesRegex(yt.YouTubeError, "unavailable"):
            yt._apply_title(pid, lambda d: True)

    def test_rejects_stale_and_refused(self):
        pid = self.draft()
        with self.assertRaisesRegex(yt.YouTubeError, "cancelled"):
            yt._apply_title(pid, lambda d: False)
        self.title = "Edit from Studio"
        with self.assertRaisesRegex(yt.YouTubeError, "changed"):
            yt._apply_title(pid, lambda d: True)
        self.assertTrue(all(c.args[0] == "GET" for c in self.request.call_args_list))

    def test_expiration(self):
        pid = self.draft()
        with patch("time.time", return_value=time.time() + yt.TTL + 5):
            with self.assertRaisesRegex(yt.YouTubeError, "expired"):
                yt._apply_title(pid, lambda d: True)

    def test_refuses_foreign_channel(self):
        self.request.side_effect = None
        self.request.return_value = {"items": [{"id": "UC" + "b" * 22}]}
        with self.assertRaisesRegex(yt.YouTubeError, "does not match"):
            yt.channel_snapshot()
        with self.assertRaisesRegex(yt.YouTubeError, "does not match"):
            yt.propose_title(VIDEO, "new")

    def test_wrong_video_owner(self):
        self.request.side_effect = [{"items": [{"id": CHANNEL}]}, {"items": [
            {**ITEM, "snippet": {**ITEM["snippet"], "channelId": "other"}}]}]
        with self.assertRaisesRegex(yt.YouTubeError, "different channel"):
            self.draft()

    def test_snapshot_pagination_and_empty_reports(self):
        self.assertEqual(yt.channel_snapshot()["channel_id"], CHANNEL)
        self.assertEqual(yt.recent_uploads(2)["videos"][0]["video_id"], VIDEO)
        self.assertEqual(self.request.call_args.kwargs["params"]["maxResults"], 2)
        result = yt.channel_report("2026-02-01", "2026-02-03")
        self.assertEqual(result["rows"], [])
        self.assertEqual(self.request.call_args.kwargs["params"]["ids"], "channel==" + CHANNEL)

    def test_input_validation_before_api(self):
        for title in ["", "x" * 101, "line\nbreak", "<bad>"]:
            with self.assertRaises(yt.YouTubeError):
                yt.propose_title(VIDEO, title)
        with self.assertRaises(yt.YouTubeError):
            yt.channel_report("2026-01-31", "2026-01-01")
        with self.assertRaises(yt.YouTubeError):
            yt.recent_uploads(51)
        with self.assertRaises(yt.YouTubeError):
            yt.propose_title("../wrong", "valid")
        with self.assertRaises(yt.YouTubeError):
            yt._apply_title("../account", lambda d: True)
        self.request.assert_not_called()


class OAuthTests(unittest.TestCase):
    def test_readonly_grant_blocks_edit_and_missing_grant_explains_onboarding(self):
        with tempfile.TemporaryDirectory() as root, patch.object(yt, "_home", return_value=Path(root)):
            with self.assertRaisesRegex(yt.YouTubeError, "connect"):
                yt._owner()
            yt._save(Path(root) / "account.json", {"scopes": [yt.READ, yt.ANALYTICS]})
            with self.assertRaisesRegex(yt.YouTubeError, "allow-title-edits"):
                yt._owner(edit=True)

    def test_loopback_flow(self):
        import threading
        from urllib.parse import parse_qs, urlsplit
        from urllib.request import urlopen

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = root / "client.json"
            client.write_text(json.dumps({"installed": {"client_id": "sample-id", "client_secret": "sample"}}))
            captured = {}

            def authorize(url):
                params = parse_qs(urlsplit(url).query)
                captured.update(params)
                callback = params["redirect_uri"][0] + "?code=approved&state=" + params["state"][0]

                def visit():
                    with urlopen(callback, timeout=5) as response:
                        response.read()

                threading.Thread(target=visit, daemon=True).start()

            reply = [{"access_token": "access", "refresh_token": "refresh",
                      "scope": " ".join([yt.READ, yt.ANALYTICS])}, {"items": [{"id": CHANNEL}]}]
            with patch.object(yt, "_home", return_value=root), patch.object(yt.webbrowser, "open", side_effect=authorize), \
                    patch.object(yt, "_request", side_effect=reply) as request, patch("builtins.print"):
                yt._connect(client, CHANNEL, False)
            self.assertEqual(captured["code_challenge_method"], ["S256"])
            self.assertIn("code_verifier", request.call_args_list[0].kwargs["data"])
            account = json.loads((root / "account.json").read_text())
            self.assertEqual(account["channel_id"], CHANNEL)
            self.assertNotIn("access_token", account)
            self.assertNotIn(yt.EDIT, account["scopes"])

    def test_error_does_not_leak_grant(self):
        response = Mock(status_code=403, text="sensitive response")
        with patch.object(httpx, "request", return_value=response):
            with self.assertRaisesRegex(yt.YouTubeError, "HTTP 403") as caught:
                yt._request("GET", yt.API)
        self.assertNotIn("sensitive", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
