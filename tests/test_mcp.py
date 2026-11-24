"""End-to-end checks using the MCP SDK against real local server processes."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError


ROOT = Path(__file__).resolve().parents[1]
SERVER = [sys.executable, "-m", "channel_ops.server"]
DEMO_TOOLS = {"campaign_brief", "demo_economics", "saas_unit_economics", "campaign_unit_economics"}
OWNER_TOOLS = {
    "create_experiment", "record_event", "experiment_report", "export_queue_draft",
    "channel_snapshot", "channel_report", "recent_uploads", "propose_title",
}
STUDY = {
    "campaign": "integration-pilot",
    "hypothesis": "One visitor pays within one day.",
    "minimum_sample": 1, "target_rate": 1.0, "window_days": 1,
}


def data(result):
    if result.isError:
        raise AssertionError(f"MCP tool returned an error: {result.content!r}")
    return json.loads(result.content[0].text)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.db = self.temp / "private" / "ledger.sqlite3"
        self.env = {"HOME": str(self.temp), "USERPROFILE": str(self.temp), "CHANNEL_OPS_DB": str(self.db)}

    async def test_stdio_owner_workflow(self):
        params = StdioServerParameters(command=SERVER[0], args=SERVER[1:], cwd=str(ROOT), env=self.env)
        with tempfile.TemporaryFile(mode="w+") as log:
            async with asyncio.timeout(30), stdio_client(params, errlog=log) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    self.assertEqual(set(tools), DEMO_TOOLS | OWNER_TOOLS)
                    for tool in tools.values():
                        self.assertNotIn("db_path", tool.inputSchema["properties"], tool.name)
                    self.assertFalse(tools["record_event"].annotations.readOnlyHint)
                    self.assertTrue(tools["experiment_report"].annotations.readOnlyHint)
                    self.assertEqual(data(await session.call_tool("create_experiment", STUDY))["campaign"], STUDY["campaign"])
                    bypass = self.temp / "client-selected.sqlite3"
                    # The SDK may reject an extra argument or discard it. It must never route the call there.
                    try:
                        await session.call_tool("experiment_report", {"campaign": STUDY["campaign"], "db_path": str(bypass)})
                    except McpError:
                        pass
                    self.assertFalse(bypass.exists())
                    args = {"campaign": STUDY["campaign"], "subject": "opaque-7", "occurred_at": "2020-06-01T10:00:00Z"}
                    exposure = {**args, "kind": "exposed", "event_id": "web:visit-7"}
                    sale = {**args, "kind": "paid", "event_id": "billing:receipt-7", "amount_cents": 2900}
                    self.assertTrue(data(await session.call_tool("record_event", exposure))["inserted"])
                    self.assertTrue(data(await session.call_tool("record_event", sale))["inserted"])
                    self.assertFalse(data(await session.call_tool("record_event", sale))["inserted"])
                    report = data(await session.call_tool("experiment_report", {"campaign": STUDY["campaign"]}))
                    self.assertEqual((report["enrolled"], report["converted"], report["decision"]), (1, 1, "threshold_met"))
                    self.assertEqual(report["cash_ledger"]["receipts_cents"], 2900)
        self.assertTrue(self.db.is_file())

    async def test_http_demo_discovery_and_owner_isolation(self):
        with socket.socket() as port_picker:
            port_picker.bind(("127.0.0.1", 0))
            port = port_picker.getsockname()[1]
        with tempfile.TemporaryFile(mode="w+") as log:
            proc = subprocess.Popen(
                [*SERVER, "--demo-http", "--port", str(port)], cwd=ROOT, env={**os.environ, **self.env},
                stdout=log, stderr=log,
            )
            try:
                async with asyncio.timeout(30):
                    while True:
                        if proc.poll() is not None:
                            log.seek(0)
                            self.fail(f"Demo exited before accepting connections: {log.read()}")
                        try:
                            _, writer = await asyncio.open_connection("127.0.0.1", port)
                        except ConnectionRefusedError:
                            await asyncio.sleep(0.05)
                            continue
                        writer.close()
                        await writer.wait_closed()
                        break
                    url = f"http://127.0.0.1:{port}/mcp"
                    async with httpx.AsyncClient(trust_env=False) as client:
                        async with streamable_http_client(url, http_client=client) as (read, write, _):
                            async with ClientSession(read, write) as session:
                                await session.initialize()
                                tools = (await session.list_tools()).tools
                                self.assertEqual({tool.name for tool in tools}, DEMO_TOOLS)
                                self.assertTrue(all(tool.annotations.readOnlyHint for tool in tools))
                                result = data(await session.call_tool("demo_economics", {}))
                                self.assertIn("campaign", result)
                                self.assertIn("subscription", result)
                                try:
                                    rejected = await session.call_tool("create_experiment", STUDY)
                                except McpError as error:
                                    self.assertIn("tool", str(error).lower())
                                else:
                                    self.assertTrue(rejected.isError)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    await asyncio.to_thread(proc.wait, 5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    await asyncio.to_thread(proc.wait)
        self.assertFalse(self.db.exists())
