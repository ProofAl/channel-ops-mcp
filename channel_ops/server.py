"""Channel Ops MCP server. Owner data is accessible only on local stdio."""
import argparse
import re

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import economics, growth, queue_export, youtube


def demo_economics() -> dict:
    """Get fully populated sample inputs and their outputs. All values are illustrative USD assumptions."""
    saas = economics.example_saas_inputs()
    campaign = economics.example_campaign_inputs()
    return {
        "subscription": {"inputs": saas, "result": economics.saas_unit_economics(saas)},
        "campaign": {"inputs": campaign, "result": economics.campaign_unit_economics(campaign)},
    }


def create_experiment(campaign: str, hypothesis: str, minimum_sample: int, target_rate: float,
                      success_event: str = "paid", window_days: int = 7) -> dict:
    """Register a private fixed cohort with lead or paid conversion, a fraction target and a window in days."""
    return growth.create_experiment(campaign, hypothesis, minimum_sample, target_rate, success_event,
                                    window_days=window_days)


def record_event(campaign: str, event_id: str, kind: str, subject: str = "", amount_cents: int = 0,
                 occurred_at: str | None = None) -> dict:
    """Record real first-party exposed, lead, paid, expense or refund evidence. Use an opaque subject and stable event ID."""
    return growth.record_event(campaign, event_id, kind, subject, amount_cents, occurred_at=occurred_at)


def experiment_report(campaign: str) -> dict:
    """Read an aggregate from the local ledger, including maturity, observations and booked cash totals."""
    return growth.experiment_report(campaign)


def _host(value: str) -> str:
    pattern = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if len(value) > 253 or not re.fullmatch(pattern, value):
        raise argparse.ArgumentTypeError("Expected a lowercase DNS hostname without scheme, port or path.")
    return value


def build_server(*, demo: bool = False, public_host: str | None = None, port: int = 8080) -> FastMCP:
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*"]
    if public_host:
        allowed_hosts.append(_host(public_host))
        allowed_origins.append("https://" + public_host)
    server = FastMCP(
        "Channel Ops", instructions=(
            "Draft campaign and PR plans and measure their first-party cash contribution. "
            "Example values are assumptions. Report YouTube data separately from sales. "
            "Never present an outreach draft, a submitted form, or a forecast as a settled payment."
        ),
        host="127.0.0.1", port=port, stateless_http=True, json_response=True, max_request_body_size=131072,
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts, allowed_origins=allowed_origins),
    )
    def add(fn, *, read=True, external=False, idempotent=True):
        hints = ToolAnnotations(readOnlyHint=read, destructiveHint=False,
                                idempotentHint=idempotent, openWorldHint=external)
        server.tool(annotations=hints, structured_output=False)(fn)

    for fn in (demo_economics, economics.saas_unit_economics, economics.campaign_unit_economics, growth.campaign_brief):
        add(fn)
    if not demo:
        add(queue_export.export_queue_draft)
        add(create_experiment, read=False)
        add(record_event, read=False)
        add(experiment_report)
        for fn in (youtube.channel_snapshot, youtube.channel_report, youtube.recent_uploads):
            add(fn, external=True)
        add(youtube.propose_title, read=False, external=True, idempotent=False)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-http", action="store_true", help="Serve only stateless example/planning tools over HTTP")
    parser.add_argument("--public-host", type=_host, help="Optional allowed public hostname of your HTTPS proxy")
    parser.add_argument("--port", type=int, default=8080, help="Local demo HTTP port (default 8080)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    if not args.demo_http and (args.public_host or args.port != 8080):
        parser.error("--public-host and --port require --demo-http")
    server = build_server(demo=args.demo_http, public_host=args.public_host, port=args.port)
    server.run("streamable-http" if args.demo_http else "stdio")


if __name__ == "__main__":
    main()
