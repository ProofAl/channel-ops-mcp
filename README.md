# Channel Ops for YouTube

For creator teams that sell a product or service. Plan a release in ChatGPT or Claude, give it a trackable call to action, then check whether the sales covered production, promotion and your team's time.

[Try the calculator](https://channel-ops-lab.knowingfoxglove4.chatgpt.site/) · [Connect a client](docs/clients.md) · [Request a pilot](https://github.com/ProofAl/channel-ops-mcp/issues/new?template=pilot.yml) · [По-русски](docs/start-ru.md)

## Try it in two minutes

Open the demo and change the example numbers. With $200 collected, $50 in fulfillment and fees and $125 spent on the campaign, the contribution is **$25**. Another $30 of editing time turns it into a **$5 loss**. The demo works without a Google account.

For a chat walkthrough, add this as a custom remote MCP connector with no authentication. The hosted demo has two tools: a campaign contribution calculator and a tagged-link builder. Use fictional inputs on the shared demo.

```text
https://channel-ops-lab.knowingfoxglove4.chatgpt.site/demo/mcp
```

> I sold two seats at $100 each. I spent $50 to deliver them and $125 to produce and promote the episode. Show the contribution, then draft a campaign link for the next episode.

## Connect an owned channel

Install Python 3.11+ and clone this repository. For a stable release, check out the version you intend to run. In a Python virtual environment:

```shell
python -m pip install .
channel-ops-mcp --help
```

Use `channel-ops-mcp` as a local stdio server or install the included native plugin in a supported client. Connect your Google desktop OAuth client to a specific YouTube channel with the local setup command. [GPT and Claude setup](docs/clients.md) · [YouTube setup](docs/youtube.md)

| Use it for | What you get |
| --- | --- |
| Channel review | Owner-authorized channel counters, recent videos and daily YouTube Analytics for the period you choose. |
| Editing | A title proposal showing the channel, video and exact change. A separate local owner command verifies the current version, applies the title and reads it back. |
| Marketing and PR | A brief with an audience, pitch, offer and tagged CTA. Export a private video or Shorts draft for an editorial queue. |
| Demand experiments | A fixed-cohort hypothesis with a target and conversion window, a private event ledger and an aggregate result. |
| Business economics | Campaign contribution, acquisition cost, payback and subscription break-even. Include refunds, fulfillment, model usage, production and support labor. |

For an owner walkthrough, ask the assistant to list the last three releases, draft a PR placement for one release, and register a measurable offer. Provide sales and cost evidence from your own systems to evaluate the outcome. If the only link is in a shared channel profile, attribute traffic at channel level. External URLs in Shorts descriptions and comments are not clickable. [YouTube link guidance](https://support.google.com/youtube/answer/13748639?hl=en)

## What decision did your last release leave open?

Did a viewer call after searching for your brand? Are you deciding which topic deserves another shoot, or explaining whether the release covered costs? Answer one question in English or Russian. The survey asks for a decision and optional role and current method. It works without a login. [Creator survey](https://channel-ops-lab.knowingfoxglove4.chatgpt.site/#survey)

For an in-chat review using your own aggregate figures, the standalone [Channel Ops Review workflow](plugins/channel-review/) reconciles tagged sales, channel-level self-reports and unknown sources. It fits a weekly editorial meeting. The local owner plugin above remains the route for reading YouTube data or proposing title changes.

## Early pilot

The code is free to self-host under MIT. We are testing demand for assisted setup and one weekly report at **US$29 per channel for the first month**. A request starts a conversation. Use the public form for non-sensitive information. Customer data, receipts and Google credentials belong on your own machine.

The first cohort is ten independent creator teams. We will record how many produce a report using their own figures, return after seven days, and pay for the pilot. [Cohort and decision rules](https://github.com/ProofAl/channel-ops-mcp/issues/1) · [Request a pilot](https://github.com/ProofAl/channel-ops-mcp/issues/new?template=pilot.yml)

[Economics and worked examples](docs/economics.md) · [First-party events](docs/growth.md) · [Editorial queue CSV](docs/queue.md) · [Market checks](docs/validation.md)

## Development

```shell
python -m unittest discover -s tests -v
node --test web/test*.mjs
```

The Python tests exercise the local MCP integration and use controlled responses for Google services. The hosted edge worker has its own protocol and calculator tests. This project is independently maintained.
