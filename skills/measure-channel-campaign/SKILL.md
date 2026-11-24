---
name: measure-channel-campaign
description: Plan or evaluate a YouTube campaign, PR pitch, or creator offer using audience, calls to action, first-party sales, and attributable costs. Use when the user wants to run a channel growth experiment, review its economics, or price a channel-management service.
---

# Measure a channel campaign

Answer in the user's language. Start from a single decision the creator can act on, such as which audience to address in the next release or whether a pilot can cover its costs. Inspect the available Channel Ops tools for this connection.

1. For a walkthrough, call `demo_economics` and label the returned data as an example. For a real campaign, establish the offer, audience and conversion event. Identify the measurement window and who owns the landing page, CRM or payment evidence.
2. Use `campaign_brief` to draft one release and its tagged call to action. For PR, choose a publication or partner that reaches the target audience, and draft a short pitch with a verifiable claim and one request. Give each placement its own tracking link or code. Distinguish prepared drafts from placements that actually ran.
3. Define a measurable prediction before looking at results. Set a success threshold, a minimum exposure or sample, a deadline and what to change if the sample is too small. For a local experiment, use the available ledger tools to register the prediction and record observations. Report a recorded experiment only after the server returns its identifier.
4. For a campaign, call `campaign_unit_economics` with first-party totals in USD for one attribution rule and time window. If conversion is necessary, establish the exchange rate and date with the user first. Deduplicate customers and payments by a stable source identifier before totaling them. Label unpaid commitments, refunds, unattributed sales and missing costs explicitly. For a subscription business, call `saas_unit_economics` with the per-channel price, service and support costs, and acquisition inputs. Preserve the units. Mark measured fields only when an evidence reference exists.
5. For an owner request, match the connected channel ID to the requested channel before fetching private reports or preparing a title edit. Show the exact before/after title, the video ID and the proposal ID. The owner applies the proposal in the local terminal. State exactly what executed. If the connection only exposes demo tools, prepare the campaign using provided inputs and explain which owner observation is missing.
6. Return the decision, the inputs that support it, and one next observation with a date or trigger. Show YouTube metrics with their source and date. Distinguish financial assumptions from measured CRM or payment data. If attribution or complete costs are missing, give a conditional result with the missing value instead of inventing a conversion or reporting profit.
