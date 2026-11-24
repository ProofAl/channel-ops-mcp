"""Single-owner YouTube integration. Network writes are reachable only from the local CLI."""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import time
import unicodedata
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx


API = "https://www.googleapis.com/youtube/v3/"
REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
TOKEN = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/"
READ = SCOPE + "youtube.readonly"
ANALYTICS = SCOPE + "yt-analytics.readonly"
EDIT = SCOPE + "youtube.force-ssl"
VIDEO = re.compile(r"[\w-]{11}", re.ASCII)
CHANNEL = re.compile(r"UC[\w-]{22}", re.ASCII)
PROPOSAL = re.compile(r"[a-f0-9]{32}")
TTL = 7 * 86400
MUTABLE_FIELDS = ("title", "description", "categoryId", "tags", "defaultLanguage")


class YouTubeError(ValueError):
    """An actionable error that does not include an access token or response body."""


def _home():
    return Path(os.environ.get("CHANNEL_OPS_YOUTUBE_HOME") or (Path.home() / ".channel-ops-youtube"))


def _save(path, payload):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        try:
            json.dump(payload, tmp, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
        except BaseException:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp.name, path)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def _request(method, url, **kwargs):
    try:
        response = httpx.request(method, url, timeout=20, **kwargs)
    except httpx.RequestError:
        raise YouTubeError("Google connection failed. Check connectivity; inspect current title before retrying an edit.") from None
    if response.status_code >= 400:
        hint = {
            400: "Check request fields and OAuth grants.",
            401: "Reconnect the Google account.",
            403: "Check API enablement, quota and approved scopes.",
            412: "Video changed. Prepare a fresh proposal.",
        }.get(response.status_code, "Review the resource in YouTube Studio before retrying.")
        raise YouTubeError(f"Google returned HTTP {response.status_code}. {hint}")
    return response.json()


class _Owner:
    def __init__(self, channel_id, access_token):
        self.channel_id = channel_id
        self.headers = {"Authorization": "Bearer " + access_token}

    def channel(self):
        response = _request("GET", API + "channels", params={
            "part": "snippet,statistics,contentDetails", "mine": "true",
        }, headers=self.headers)
        for item in response.get("items", []):
            if item["id"] == self.channel_id:
                return item
        raise YouTubeError("Google's authorized channel does not match the configured YouTube channel ID.")

    def video(self, video_id):
        if not VIDEO.fullmatch(video_id):
            raise YouTubeError("Expected an 11-character YouTube video ID.")
        data = _request("GET", API + "videos", params={"id": video_id, "part": "snippet"}, headers=self.headers)
        for item in data.get("items", []):
            if item["id"] == video_id and item["snippet"]["channelId"] == self.channel_id:
                if not item.get("etag"):
                    raise YouTubeError("YouTube omitted the video revision. Prepare the edit in Studio.")
                return item
        raise YouTubeError("This video is unavailable or belongs to a different channel.")


def _owner(edit=False):
    try:
        credentials = json.loads((_home() / "account.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise YouTubeError("Connect a channel with python -m channel_ops.youtube connect first.") from None
    if edit and EDIT not in credentials["scopes"]:
        raise YouTubeError("Reconnect locally with --allow-title-edits to enable approved edits.")
    grant = _request("POST", TOKEN, data={
        "client_id": credentials["client_id"], "client_secret": credentials["client_secret"],
        "refresh_token": credentials["refresh_token"], "grant_type": "refresh_token",
    })
    return _Owner(credentials["channel_id"], grant["access_token"])


def channel_snapshot():
    """Fetch the pinned owner's current public counters; missing fields remain absent."""
    item = _owner().channel()
    return {"source": "YouTube Data API", "channel_id": item["id"],
            "title": item["snippet"]["title"], "statistics": item["statistics"]}


def recent_uploads(limit: int = 10):
    """List the first page of recent videos from the pinned owner's uploads playlist."""
    if not 1 <= limit <= 50:
        raise YouTubeError("limit must be between 1 and 50.")
    owner = _owner()
    uploads = owner.channel()["contentDetails"]["relatedPlaylists"]["uploads"]
    data = _request("GET", API + "playlistItems", headers=owner.headers, params={
        "playlistId": uploads, "part": "snippet,contentDetails", "maxResults": limit,
    })
    return {"source": "YouTube Data API", "channel_id": owner.channel_id, "videos": [
        {"video_id": row["contentDetails"]["videoId"], "title": row["snippet"]["title"],
         "published_at": row["contentDetails"].get("videoPublishedAt")}
        for row in data.get("items", [])
    ]}


def channel_report(start_date: str, end_date: str):
    """Return dated rows for the pinned channel. Missing days have unknown activity."""
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError:
        raise YouTubeError("Use ISO dates such as 2026-01-31.") from None
    if end < start:
        raise YouTubeError("end_date must be on or after start_date.")
    owner = _owner()
    owner.channel()
    response = _request("GET", REPORTS, headers=owner.headers, params={
        "ids": "channel==" + owner.channel_id, "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": "day", "sort": "day", "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost",
    })
    columns = [field["name"] for field in response["columnHeaders"]]
    return {"source": "YouTube Analytics API", "channel_id": owner.channel_id,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "columns": columns, "rows": response.get("rows", [])}


def _validate_title(title):
    if (not title.strip() or len(title) > 100 or "<" in title or ">" in title or
            any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in title)):
        raise YouTubeError("Use a visible title of 1–100 characters without angle brackets or control characters.")


def _purge_expired():
    folder = _home() / "proposals"
    if folder.is_dir():
        for path in folder.glob("*.json"):
            if PROPOSAL.fullmatch(path.stem):
                try:
                    if path.stat().st_mtime < time.time() - TTL:
                        path.unlink(missing_ok=True)
                except FileNotFoundError:
                    continue


def propose_title(video_id: str, title: str):
    """Save a private draft. Applying it requires a separate local owner command."""
    _validate_title(title)
    if not VIDEO.fullmatch(video_id):
        raise YouTubeError("Expected an 11-character YouTube video ID.")
    owner = _owner()
    owner.channel()
    item = owner.video(video_id)
    if title == item["snippet"]["title"]:
        raise YouTubeError("The proposed title is already set.")
    _purge_expired()
    proposal = {"proposal_id": secrets.token_hex(16), "channel_id": owner.channel_id, "video_id": video_id,
                "before": item["snippet"]["title"], "after": title, "etag": item["etag"],
                "expires": int(time.time()) + TTL}
    _save(_home() / "proposals" / (proposal["proposal_id"] + ".json"), proposal)
    return {key: value for key, value in proposal.items() if key != "etag"}


def _apply_title(proposal_id, confirm):
    if not PROPOSAL.fullmatch(proposal_id):
        raise YouTubeError("Invalid proposal ID.")
    path = _home() / "proposals" / (proposal_id + ".json")
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise YouTubeError("Proposal unavailable. Generate a fresh proposal.") from None
    if draft["expires"] <= time.time():
        path.unlink(missing_ok=True)
        raise YouTubeError("Proposal expired. Generate a fresh proposal.")
    owner = _owner(edit=True)
    if owner.channel_id != draft["channel_id"]:
        raise YouTubeError("Proposal was prepared for a different channel.")
    owner.channel()
    _validate_title(draft["after"])
    if not confirm(draft):
        raise YouTubeError("Edit cancelled.")
    item = owner.video(draft["video_id"])
    current = item["snippet"]
    if item["etag"] != draft["etag"] or current["title"] != draft["before"]:
        raise YouTubeError("Video changed since drafting. Review a fresh proposal.")
    # videos.update replaces mutable fields inside each requested part.
    # Only "snippet" is included; categoryId is always required.
    if not current.get("categoryId") or "description" not in current:
        raise YouTubeError("Incomplete video snippet. Review the edit in YouTube Studio.")
    snippet = {key: current[key] for key in MUTABLE_FIELDS if key in current}
    snippet["title"] = draft["after"]
    etag = item["etag"]
    if not etag.startswith(('"', 'W/"')):
        etag = '"' + etag + '"'
    _request("PUT", API + "videos", params={"part": "snippet"},
             headers={**owner.headers, "If-Match": etag}, json={"id": item["id"], "snippet": snippet})
    verified = owner.video(item["id"])["snippet"]
    if any(verified.get(key) != value for key, value in snippet.items()):
        raise YouTubeError("Update returned, but read-back differs. Review the video in Studio.")
    path.unlink(missing_ok=True)
    return {"channel_id": owner.channel_id, "video_id": item["id"], "title": verified["title"], "verified": True}


def _connect(client_file, channel_id, allow_title_edits):
    if not CHANNEL.fullmatch(channel_id):
        raise YouTubeError("Use the full YouTube channel ID beginning with UC.")
    config = json.loads(client_file.read_text(encoding="utf-8")).get("installed", {})
    if not config.get("client_id") or not config.get("client_secret"):
        raise YouTubeError("Use the Google Cloud OAuth desktop client JSON.")
    verifier, state = secrets.token_urlsafe(64), secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    outcome = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # The URL contains a short-lived authorization code.

        def do_GET(self):
            target = urlsplit(self.path)
            args = parse_qs(target.query)
            if target.path != "/callback" or args.get("state") != [state]:
                self.send_error(400)
                return
            outcome["code"] = args.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Return to the local terminal for the result. You can close this tab.")

    requested = [READ, ANALYTICS]
    if allow_title_edits:
        requested.append(EDIT)
    with HTTPServer(("127.0.0.1", 0), Callback) as listener:
        redirect = f"http://127.0.0.1:{listener.server_port}/callback"
        authorization = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": config["client_id"], "redirect_uri": redirect, "response_type": "code",
            "scope": " ".join(requested), "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent select_account",
        })
        print("Choose the owner account and channel in your browser. If it did not open, visit\n" + authorization)
        webbrowser.open(authorization)
        listener.timeout = 1
        deadline = time.monotonic() + 240
        while not outcome and time.monotonic() < deadline:
            listener.handle_request()
    if not outcome.get("code"):
        raise YouTubeError("Authorization timed out or was declined.")
    grant = _request("POST", TOKEN, data={
        "client_id": config["client_id"], "client_secret": config["client_secret"], "code": outcome["code"],
        "code_verifier": verifier, "grant_type": "authorization_code", "redirect_uri": redirect,
    })
    scopes = set(grant.get("scope", "").split())
    if not set(requested) <= scopes or not grant.get("refresh_token"):
        raise YouTubeError("Google did not grant the requested scopes and offline access. Reconnect.")
    _Owner(channel_id, grant["access_token"]).channel()
    _save(_home() / "account.json", {"channel_id": channel_id, "client_id": config["client_id"],
          "client_secret": config["client_secret"], "refresh_token": grant["refresh_token"], "scopes": requested})
    return {"channel_id": channel_id, "title_edits_enabled": allow_title_edits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    connect = commands.add_parser("connect", help="Bind a desktop OAuth client to one YouTube channel")
    connect.add_argument("--client-file", type=Path, required=True)
    connect.add_argument("--channel-id", required=True)
    connect.add_argument("--allow-title-edits", action="store_true")
    apply = commands.add_parser("apply-title", help="Review and apply one title proposal")
    apply.add_argument("proposal_id")
    commands.add_parser("disconnect", help="Remove stored credentials and local title drafts")
    args = parser.parse_args()
    try:
        if args.command == "connect":
            result = _connect(args.client_file, args.channel_id, args.allow_title_edits)
        elif args.command == "disconnect":
            (_home() / "account.json").unlink(missing_ok=True)
            for path in (_home() / "proposals").glob("*.json"):
                if PROPOSAL.fullmatch(path.stem):
                    path.unlink(missing_ok=True)
            result = {"local_credentials_removed": True}
        else:
            if not sys.stdin.isatty():
                raise YouTubeError("Owner approval requires an interactive local terminal.")
            def confirm(proposal):
                preview = {key: proposal[key] for key in ("channel_id", "video_id", "before", "after")}
                display = json.dumps(preview, indent=2, ensure_ascii=False)
                print("".join(c if unicodedata.category(c) != "Cf" else ascii(c)[1:-1] for c in display))
                return input("To publish, type the video ID shown above: ").strip() == proposal["video_id"]
            result = _apply_title(args.proposal_id, confirm)
        print(json.dumps(result, ensure_ascii=False))
    except (YouTubeError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
