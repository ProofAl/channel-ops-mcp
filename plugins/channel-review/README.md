# Channel Ops Review

A standalone workflow for deciding whether to make another video on the same topic. Supply aggregate order, refund and cost figures in the chat. The workflow separates release-linked payments from customers who recall the channel and shows how much the release contributed after direct costs.

**Try it in English.** “Our landing page shows four coded purchases. Three buyers also said YouTube on a call. How many orders can I credit, and did the tutorial pay for itself?”

**Попробовать по-русски.** «Мы посчитали оплаты по ссылке и опросили покупателей. Часть людей есть в обоих списках. Помоги оценить вклад ролика и выбрать тему следующего выпуска».

The [worked case](skills/review-video-contribution/references/worked-case.md) starts with ten paid orders, resolves overlap and distinguishes $30 of contribution linked to one release from a broader $120 channel scenario.

## Use it

Load this directory as a standalone Claude Code plugin with `claude --plugin-dir ./plugins/channel-review` from a repository checkout. The `review-video-contribution` folder can also be used as a standard agent skill. The package runs within the assistant from the figures the user shares. It requires no YouTube credentials, Python runtime, external tools or uploads to Channel Ops.

The downloadable plugin ZIP contains the skill, icon, metadata and license. The root of this repository separately provides the Channel Ops MCP server for people who want to connect their own channel. Each product has its own tool and credential requirements.

### Use it today

You can use the review directly in an ordinary conversation. Open the [workflow text](skills/review-video-contribution/SKILL.md), copy it into your chat, then provide aggregate figures for one video. For example: “My video brought $400 in release-coded payments, $100 was refunded, fulfillment cost $40, and production cost $230. Did the release cover its costs?” A complete set of those direct costs gives a $30 contribution.

For persistent installation, add this repository as a plugin marketplace in Codex or Claude Code and select **Channel Ops Review**. Codex: `codex plugin marketplace add ProofAl/channel-ops-mcp`, then `codex plugin add channel-ops-review@channel-ops`. Claude Code: `claude plugin marketplace add ProofAl/channel-ops-mcp`, then `claude plugin install channel-ops-review@channel-ops`. The [release ZIP](https://github.com/ProofAl/channel-ops-mcp/releases/download/review-v0.1.0/channel-review.zip) is also available for compatible plugin import and publisher review.

To generate the skills-only distribution from this repository:

```shell
python plugins/channel-review/build.py dist/channel-review.zip
```

A validated ZIP can be uploaded through the publisher's OpenAI plugin dashboard. Public availability depends on the verified publisher account, review and publication. The MCP server is a separate submission. [OpenAI plugin submission](https://developers.openai.com/plugins/deploy/submission)

## Check invocation and results

| Example request | Expected behavior |
| --- | --- |
| “The tutorial has 4 orders, of which 1 was refunded. Did it earn back $230?” | Ask for the missing receipts and variable costs, then calculate a release-linked subtotal. |
| “12 orders, 5 coded, 6 recalled YouTube. I don't know the overlap.” | If the counts refer to one population, report a range of 6–11 orders covered by either signal. The monetary amount requires sales information. |
| “Two buyers named our channel without naming the episode. Which video should we repeat?” | Preserve channel-level attribution. Give a small comparison test until release-level evidence is available. |
| «Оплаты по промокоду $400, возвраты $100, исполнение $40, выпуск $230. Окупился ли выпуск?» | Return $30 contribution if inputs cover all direct costs, with formula and decision in Russian. |
| “Use this video's sales figures as an example in a sponsor email.” | Use the workflow only if the user also requests economic reconciliation. For a writing-only request, draft the email from the supplied figures. |
| “Upload a new thumbnail and change the title.” | This chat-only workflow has no publishing capability. Route the request to the user's available channel-management workflow. |
| “Generate ten titles for my vlog.” | For an ideation-only request, use ordinary writing help. |
