# Connect Channel Ops

| Goal | Connection | First prompt |
| --- | --- | --- |
| Try the hosted demo in ChatGPT or Claude on the web | Add the public connector below | “Calculate a sample campaign with $1,000 collected, $50 refunded, $250 delivery and fees, and $400 campaign costs.” |
| Model subscription pricing or a full campaign in a web client | Connect your own Python demo server | “Compare break-even at $19 and $29 per channel.” |
| Manage your own channel or keep a persistent experiment ledger | Run the checkout locally with Claude Code or a compatible local MCP client | “Check which YouTube channel is connected and list its last three releases.” |
| Try the native workflow in ChatGPT desktop or Codex | Add the repository marketplace on a local executor | “Plan a launch for my next video, including how to count paid customers.” |

## Install the local server

Open the project directory, activate the Python environment you want the client to use, and install the server.

```shell
python -m pip install .
channel-ops-mcp --help
```

The bundled plugin manifests launch the installed `channel-ops-mcp` command over stdio. Start the client with that environment on its executable search path. For desktop clients that don't inherit your shell's environment, configure the absolute path to the installed executable. On Windows, `(Get-Command channel-ops-mcp).Source` in PowerShell prints it. On macOS or Linux, use `command -v channel-ops-mcp`.

### Claude Code

With the Python environment active, launch Claude Code from the root of the checkout.

```shell
claude --plugin-dir .
```

Enter `/channel-ops-mcp:measure-channel-campaign` to use the bundled workflow. To keep the plugin across sessions, register the local marketplace and install from it.

```shell
claude plugin marketplace add .
claude plugin install channel-ops-mcp@channel-ops
```

After adding a plugin, start a new session and check `/mcp` for the server. You can also configure the same command in Claude Desktop under local MCP servers. Add this entry to the desktop MCP configuration.

```json
{
  "mcpServers": {
    "channel-ops": {
      "command": "channel-ops-mcp"
    }
  }
}
```

Replace the command with its absolute executable path in a desktop configuration where needed. Then restart the client. [Claude Code installation](https://code.claude.com/docs/en/plugins/install) · [Claude local connectors](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

### ChatGPT desktop and Codex

The checkout includes a portable `plugin.json`, a stdio `mcp.json`, the workflow, and a repository marketplace. Run this command from the checkout to add it as a local source.

```shell
codex plugin marketplace add .
codex plugin add channel-ops-mcp@channel-ops
codex plugin list --marketplace channel-ops
```

You can also install through the Plugins directory in a ChatGPT desktop client that supports local execution. Select the **Channel Ops** marketplace, install **Channel Ops**, and open a fresh conversation. Test with “Show the example economics,” then try the campaign workflow. [OpenAI plugin installation and local marketplaces](https://developers.openai.com/plugins/build/plugins)

### Authorize your channel

Use a Google Cloud Desktop OAuth client with the YouTube Data API v3 and YouTube Analytics API enabled. Keep its downloaded JSON on your own machine. In the activated environment, replace the example file path and channel ID below.

```shell
python -m channel_ops.youtube connect --client-file "desktop-client.json" --channel-id "YOUR_CHANNEL_ID"
```

Choose the intended YouTube channel in the browser. Read access allows an owner to request channel counters, recent videos and daily Analytics. To enable title changes, repeat the local connect command with `--allow-title-edits`. Ask the client to prepare a title proposal, inspect the returned video ID and exact title change, then run the local command below with the returned proposal ID. The command displays the change and requests your confirmation.

```shell
python -m channel_ops.youtube apply-title PROPOSAL_ID
```

Use `python -m channel_ops.youtube disconnect` to remove the locally stored Google account and proposals. [Detailed YouTube setup and revocation](youtube.md) · [Google OAuth authorization](https://developers.google.com/youtube/v3/guides/authentication)

## Try the hosted demo in ChatGPT or Claude

Copy this complete URL into the connector settings. The hosted demo works with fictional figures and public landing-page URLs without a Google account.

```text
https://channel-ops-lab.knowingfoxglove4.chatgpt.site/demo/mcp
```

| Client | Setup |
| --- | --- |
| ChatGPT web | Open **Plugins → + → Add custom MCP server**. Paste the URL above, select no authentication, then **Create as a plugin**. Open a new conversation and select the plugin. |
| Claude web | Open **Customize → Connectors → Add custom connector**. Paste the URL above, choose **No sign in**, add the connector and enable it in a conversation. Workspace owners may need to add it first. |

The hosted connector exposes two tools. Try either prompt.

| Tool | Prompt | Expected result |
| --- | --- | --- |
| `demo_contribution` | “Calculate an example with $1,000 collected, $50 refunded, $250 delivery and fees, and $400 total campaign costs.” | $950 net receipts and $300 campaign contribution. |
| `draft_campaign_link` | “Tag the public page https://example.org/audit for the organic YouTube campaign called audit-pilot.” | A draft URL with `utm_source=youtube`, `utm_medium=organic_video` and `utm_campaign=audit-pilot`. |

For the browser version use the launch page. For exact steps on adding an MCP connection, see the client guides. [Launch page](https://channel-ops-lab.knowingfoxglove4.chatgpt.site/) · [ChatGPT connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt) · [Claude connection guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

## Self-host the four-tool Python demo

To run the full calculators and PR brief generator in a web client, host the Python server behind an HTTPS reverse proxy or development tunnel you control. Set `--public-host` to its public DNS hostname and forward HTTPS traffic to the local service. Replace `demo.example.com` below with that hostname.

```shell
channel-ops-mcp --demo-http --public-host demo.example.com
```

The default listener is `127.0.0.1:8080`. Register your own `https://demo.example.com/mcp` URL on standard HTTPS port 443 using the client steps above. This deployment exposes `demo_economics`, `campaign_brief`, `saas_unit_economics` and `campaign_unit_economics`. Owner credentials, YouTube operations and the local ledger stay on the stdio path.

Try “Show the sample business model. Compare monthly contribution at $19 and $29 with the other assumptions held constant.” For a PR test, try “Draft a pitch for a creator newsletter offering a 15-minute channel audit. Link to https://example.org/audit and tag it as the newsletter pilot.”

## Directory distribution

Repository marketplaces allow users to install directly. Listing in the OpenAI or Anthropic public directories is a separate submission and review. OpenAI requires a stable public HTTPS endpoint for its remote submission route. Anthropic accepts a remote connector URL or a GitHub plugin bundle. [OpenAI submission](https://developers.openai.com/plugins/deploy/submission) · [Claude submission](https://claude.com/resources/articles/build-plugins-for-claude)
