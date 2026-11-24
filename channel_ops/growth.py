"""First-party campaign briefs and a durable, single-workspace experiment ledger."""

from __future__ import annotations

import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TAG = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
_OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:-]{0,119}")
_KINDS = {"exposed", "lead", "paid", "expense", "refund"}
_EVENT_KEYS = {"campaign", "event_id", "kind", "subject", "amount_cents", "occurred_at"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS growth_experiments (
  campaign TEXT PRIMARY KEY,
  hypothesis TEXT NOT NULL,
  minimum_sample INTEGER NOT NULL,
  target_rate REAL NOT NULL,
  success_event TEXT NOT NULL,
  window_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS growth_events (
  event_id TEXT PRIMARY KEY,
  campaign TEXT NOT NULL REFERENCES growth_experiments(campaign),
  kind TEXT NOT NULL,
  subject TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS growth_events_cohort
ON growth_events(campaign, kind, subject, occurred_at);
"""


def _tag(value):
    if not isinstance(value, str) or not _TAG.fullmatch(value):
        raise ValueError("Use a lowercase slug with letters, numbers, hyphens or underscores (1–80 characters).")
    return value


def _line(value, field, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or not value.isprintable():
        raise ValueError(f"{field} must be a nonempty single line of at most {maximum} characters.")
    return value.strip()


def _time(value):
    if not isinstance(value, str):
        raise ValueError("An event timestamp must include its UTC offset.")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Use an ISO 8601 timestamp with a UTC offset.") from exc
    if dt.utcoffset() is None:
        raise ValueError("An event timestamp must include its UTC offset.")
    return dt.astimezone(timezone.utc)


def campaign_brief(campaign: str, destination: str, source: str, medium: str,
                   audience: str, angle: str, offer: str, cta: str) -> dict:
    """Build a reusable PR pitch and tagged CTA without publishing or fetching URLs."""
    campaign, source, medium = map(_tag, (campaign, source, medium))
    destination = _line(destination, "destination", 2000)
    if any(char.isspace() for char in destination) or '\\' in destination:
        raise ValueError("Supply a URL with encoded spaces and valid path separators.")
    url = urlsplit(destination)
    # Accessing the port also validates a numeric, in-range value.
    _ = url.port
    if url.scheme != "https" or not url.hostname or url.username is not None or url.password is not None:
        raise ValueError("Supply an HTTPS landing-page URL without embedded credentials.")
    fields = {"utm_source": source, "utm_medium": medium, "utm_campaign": campaign}
    params = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k.lower() not in fields]
    tagged = urlunsplit(url._replace(query=urlencode([*params, *fields.items()])))
    audience, angle, offer, cta = (_line(v, k) for k, v in
                                 (("audience", audience), ("angle", angle), ("offer", offer), ("cta", cta)))
    return {
        "campaign": campaign, "source": source, "medium": medium, "url": tagged,
        "audience": audience, "angle": angle, "offer": offer, "cta": cta,
        "pitch_draft": f"{angle}\n\n{offer}\n\n{cta}\n{tagged}",
        "distribution": "draft",
    }


@contextmanager
def _database(db_path):
    explicit = db_path or os.environ.get("CHANNEL_OPS_DB")
    path = Path(explicit).expanduser() if explicit else Path.home() / ".local/share/channel-ops-mcp/growth.sqlite3"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # sqlite creates files with the process umask. Create the owner-only file first.
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    os.close(fd)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        with conn:
            yield conn
    finally:
        conn.close()


def _study(conn, campaign):
    record = conn.execute("SELECT * FROM growth_experiments WHERE campaign=?", (_tag(campaign),)).fetchone()
    if record is None:
        raise ValueError("Unknown campaign. Register its experiment first.")
    return dict(record)


def create_experiment(campaign: str, hypothesis: str, minimum_sample: int, target_rate: float,
                      success_event: str = "paid", db_path=None, *, window_days: int = 7) -> dict:
    """Register a fixed cohort and conversion deadline per subject; repeated identical calls are safe."""
    campaign = _tag(campaign)
    hypothesis = _line(hypothesis, "hypothesis")
    if type(minimum_sample) is not int or not 1 <= minimum_sample <= 1_000_000:
        raise ValueError("minimum_sample must be a whole number from 1 to 1000000.")
    if type(target_rate) not in (int, float) or not math.isfinite(target_rate) or not 0 < target_rate <= 1:
        raise ValueError("target_rate must be a fraction greater than 0 and at most 1.")
    if success_event not in {"lead", "paid"}:
        raise ValueError("Use lead or paid for the eligible success event.")
    if type(window_days) is not int or not 1 <= window_days <= 365:
        raise ValueError("window_days must be a whole number from 1 to 365.")
    spec = dict(campaign=campaign, hypothesis=hypothesis, minimum_sample=minimum_sample,
                target_rate=target_rate, success_event=success_event, window_days=window_days)
    with _database(db_path) as conn:
        conn.execute("""
            INSERT INTO growth_experiments(campaign,hypothesis,minimum_sample,target_rate,success_event,window_days)
            VALUES(:campaign,:hypothesis,:minimum_sample,:target_rate,:success_event,:window_days)
            ON CONFLICT(campaign) DO NOTHING
        """, spec)
        if _study(conn, campaign) != spec:
            raise ValueError("Campaign already has a different registered hypothesis. Use a new campaign slug.")
    return spec


def _insert(conn, campaign, event_id, kind, subject, amount_cents, occurred_at):
    if not isinstance(event_id, str) or not _OPAQUE.fullmatch(event_id):
        raise ValueError("Use a stable opaque event ID.")
    if kind not in _KINDS:
        raise ValueError("Unknown event kind.")
    if not isinstance(subject, str) or (subject and not _OPAQUE.fullmatch(subject)) or (kind != "expense" and not subject):
        raise ValueError("Supply an opaque subject ID for audience, receipt and refund events.")
    if kind == "expense" and subject:
        raise ValueError("Leave subject empty for campaign expenses.")
    if type(amount_cents) is not int or not 0 <= amount_cents <= 1_000_000_000_000:
        raise ValueError("amount_cents must be a nonnegative whole number in USD cents.")
    if (kind in {"paid", "expense", "refund"}) != (amount_cents > 0):
        raise ValueError("Receipts, expenses and refunds need a positive amount; other events have zero amount.")
    now = datetime.now(timezone.utc)
    ts = _time(occurred_at) if occurred_at is not None else now
    if ts > now:
        raise ValueError("Future events are ineligible.")
    event = dict(campaign=campaign, event_id=event_id, kind=kind, subject=subject,
                 amount_cents=amount_cents, occurred_at=ts.isoformat(timespec="microseconds"))
    cursor = conn.execute("""
        INSERT INTO growth_events(event_id,campaign,kind,subject,amount_cents,occurred_at)
        VALUES(:event_id,:campaign,:kind,:subject,:amount_cents,:occurred_at)
        ON CONFLICT(event_id) DO NOTHING
    """, event)
    if cursor.rowcount:
        return True
    previous = dict(conn.execute("SELECT * FROM growth_events WHERE event_id=?", (event_id,)).fetchone())
    if occurred_at is None:
        event["occurred_at"] = previous["occurred_at"]
    if event != previous:
        raise ValueError("Event ID was already used with different evidence.")
    return False


def record_event(campaign: str, event_id: str, kind: str, subject: str = "", amount_cents: int = 0,
                 db_path=None, *, occurred_at: str | None = None) -> dict:
    """Record first-party evidence exactly once. Use the same ID on delivery retry."""
    with _database(db_path) as conn:
        _study(conn, campaign)
        created = _insert(conn, campaign, event_id, kind, subject, amount_cents, occurred_at)
    return {"campaign": campaign, "event_id": event_id, "inserted": created}


def export_events(campaign: str, db_path=None) -> list[dict]:
    """Owner-only adapter export. Use an authenticated, private data path."""
    with _database(db_path) as conn:
        _study(conn, campaign)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM growth_events WHERE campaign=? ORDER BY occurred_at,event_id", (campaign,)
        )]


def import_events(campaign: str, events: list[dict], db_path=None) -> dict:
    """Import an exported batch atomically; reject conflicts rather than silently overwriting evidence."""
    if not isinstance(events, list) or len(events) > 10_000:
        raise ValueError("Supply a list with at most 10000 events per batch.")
    with _database(db_path) as conn:
        _study(conn, campaign)
        inserted = 0
        for event in events:
            if not isinstance(event, dict) or set(event) != _EVENT_KEYS or event["campaign"] != campaign:
                raise ValueError("Invalid event shape or campaign for this batch.")
            if not isinstance(event["occurred_at"], str):
                raise ValueError("Each imported event needs an explicit timestamp.")
            inserted += _insert(conn, **event)
    return {"campaign": campaign, "inserted": inserted, "duplicates": len(events) - inserted}


def experiment_report(campaign: str, db_path=None) -> dict:
    """Score the first N distinct subjects from first exposure; include receipts for all campaign traffic."""
    now = datetime.now(timezone.utc)
    with _database(db_path) as conn:
        conn.execute("BEGIN")
        study = _study(conn, campaign)
        cohort = conn.execute("""
            SELECT subject, MIN(occurred_at) AS first_seen FROM growth_events
            WHERE campaign=? AND kind='exposed' GROUP BY subject
            ORDER BY first_seen, subject LIMIT ?
        """, (campaign, study["minimum_sample"])).fetchall()
        first_seen = {row["subject"]: _time(row["first_seen"]) for row in cohort}
        window = timedelta(days=study["window_days"])
        successes = set()
        for row in conn.execute(
            "SELECT subject, occurred_at FROM growth_events WHERE campaign=? AND kind=?", (campaign, study["success_event"])
        ):
            start = first_seen.get(row["subject"])
            if start is not None and start <= _time(row["occurred_at"]) < start + window:
                successes.add(row["subject"])
        amounts = {r["kind"]: r["total"] for r in conn.execute("""
            SELECT kind,SUM(amount_cents) AS total FROM growth_events WHERE campaign=?
            AND kind IN ('paid','expense','refund') GROUP BY kind
        """, (campaign,))}
    enrolled = len(cohort)
    matured = sum(start + window <= now for start in first_seen.values())
    rate = len(successes) / enrolled if enrolled else None
    if enrolled < study["minimum_sample"]:
        decision = "collecting"
    elif matured < enrolled:
        decision = "awaiting_window"
    else:
        decision = "threshold_met" if rate >= study["target_rate"] else "below_threshold"
    paid, expenses, refunds = (amounts.get(k, 0) for k in ("paid", "expense", "refund"))
    return {
        **study, "as_of": now.isoformat(), "decision": decision,
        "enrolled": enrolled, "matured": matured, "converted": len(successes), "observed_rate": rate,
        "cash_ledger": {"currency": "USD", "receipts_cents": paid, "refunds_cents": refunds,
                        "recorded_costs_cents": expenses, "net_after_recorded_costs_cents": paid - refunds - expenses},
    }
