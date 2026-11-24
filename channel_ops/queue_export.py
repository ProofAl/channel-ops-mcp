"""Export a single private YouTube draft for review in a social content queue."""

import csv
import io
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


COLUMNS = (
    "content_id", "channel", "scheduled_at", "status", "pillar", "text",
    "link_url", "utm_campaign", "published_at", "remote_post_id", "last_error",
    "origin", "target_id", "media_ref", "visibility", "evidence_ref",
)


def _field(name: str, value: str, *, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if multiline:
        value = value.replace("\r\n", "\n")
    allowed_controls = {"\u200c", "\u200d"}  # Script and emoji joining characters.
    if multiline:
        allowed_controls.add("\n")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} and c not in allowed_controls
           for c in value):
        raise ValueError(f"{name} contains unsupported control characters")
    value = value.strip()
    # CSV quoting does not stop spreadsheet programs evaluating a cell.
    if unicodedata.normalize("NFKC", value).startswith(("=", "+", "-", "@")):
        raise ValueError(f"{name} starts with a spreadsheet formula prefix")
    return value


def _identifier(name: str, value: str, pattern: str) -> str:
    value = _field(name, value)
    if not re.fullmatch(pattern, value):
        raise ValueError(f"Invalid {name}")
    return value


def export_queue_draft(
    *, content_id: str, title: str, description: str, target_id: str,
    media_ref: str, evidence_ref: str, channel: str = "youtube", pillar: str = "",
    link_url: str = "", utm_campaign: str = "",
) -> str:
    """Return a UTF-8-ready CSV string with one header and one unscheduled draft."""
    if channel not in ("youtube", "youtube_shorts"):
        raise ValueError("channel must be youtube or youtube_shorts")
    content_id = _identifier("content_id", content_id, r"[a-z0-9][a-z0-9-]{3,63}")
    target_id = _identifier("target_id", target_id, r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}")
    media_ref = _identifier("media_ref", media_ref, r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}")
    evidence_ref = _identifier("evidence_ref", evidence_ref, r"#[0-9]{1,6}|[a-zA-Z0-9][a-zA-Z0-9._/#-]{2,79}")
    title = _field("title", title)
    if not 1 <= len(title) <= 100:
        raise ValueError("title must have 1–100 characters")
    # The description shares a CSV cell with the title, so a leading list marker is safe.
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    text = _field("text", title + "\n" + description, multiline=True)
    body = text.partition("\n")[2]
    pillar = _field("pillar", pillar)
    utm_campaign = _field("utm_campaign", utm_campaign)
    link_url = _field("link_url", link_url)
    if link_url:
        url = urlsplit(link_url)
        if (url.scheme != "https" or not url.hostname or url.username is not None or
                url.password is not None or "\\" in link_url or any(c.isspace() for c in link_url)):
            raise ValueError("link_url must be an HTTPS destination without embedded credentials")
        tracking = {"utm_source": channel, "utm_medium": "organic_social",
                    "utm_campaign": utm_campaign or "organic", "utm_content": content_id}
        parameters = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k not in tracking]
        tracked = urlunsplit(url._replace(query=urlencode(parameters + list(tracking.items()))))
        body = (body + "\n\n" + tracked).strip()
    if len(body.encode("utf-8")) > 5000:
        raise ValueError("description including the tracking link exceeds 5000 UTF-8 bytes")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow({
        "content_id": content_id, "channel": channel, "status": "draft",
        "pillar": pillar, "text": text, "link_url": link_url, "utm_campaign": utm_campaign,
        "origin": "control", "target_id": target_id, "media_ref": media_ref,
        "visibility": "private", "evidence_ref": evidence_ref,
    })
    return output.getvalue()
