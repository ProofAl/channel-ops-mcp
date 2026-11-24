# Unit economics for a channel and a campaign

Use these two models to answer different purchase decisions. The first asks whether a team can profitably serve a paying channel. The second asks whether a creator earned back the cost of a specific video or campaign. Both use USD excluding sales taxes. These sample inputs are illustrative assumptions. All figures below can be reproduced without a Google connection.

## One paying channel per month

Start with [the monthly inputs](../examples/saas-inputs.json). Monthly contribution is revenue after refunds, less processing, storage and compute, paid model calls, other direct service costs and support labor. Processing is charged on the original price with one successful billing event per month. Enter fully loaded hourly rates, including taxes and benefits on labor where applicable. If a customer pays for their own model, enter zero for seller-paid model calls.

Acquisition includes paid promotion, distribution software allocated to acquisition, sales and onboarding labor. Divide the full cohort spend by new paying channels attributable to that cohort. Use matching periods, allowing time for conversions. A paying channel counts once per acquisition. Charge ongoing support after onboarding to the monthly service model.

Each price scenario assumes refunds of 3%, processing of 3% + $0.30, compute and storage of $1.20, model calls of $1.50, and other service costs of $0.50 per channel/month. Loaded support and acquisition labor cost $30/hour. Acquisition spends $180 cash and eight hours for 12 paying channels, giving $35 CAC. Monthly channel churn is 5%. The $300/month fixed-cost assumption covers the example allocation of product engineering, overhead and infrastructure shared across accounts. Replace it with an operating budget that includes development recovery and ongoing maintenance before making a scale decision.

| Price/month | Support/channel/month | Contribution/channel/month | Simple CAC payback | Contribution after churn replacement | Channels to cover $300/month |
| ---: | ---: | ---: | ---: | ---: | ---: |
| $19 | 10 min | $9.36 | 3.74 mo | $7.61 | 40 |
| $29 | 10 min | $18.76 | 1.87 mo | $17.01 | 18 |
| $19 | 30 min | −$0.64 | Unreachable | −$2.39 | Unreachable |
| $29 | 30 min | $8.76 | 4.00 mo | $7.01 | 43 |

Simple payback is CAC divided by monthly contribution while a channel remains subscribed. Lifetime contribution assumes constant monthly churn and contribution, has no discounting, and equals monthly contribution divided by monthly churn. It describes a scenario until retention is observed in successive paid cohorts. Steady-state break-even includes replacement acquisition for churned channels each month, calculated as CAC × monthly churn × active channels. Growth acquisition and financing costs require their own cash budget.

## One content or PR campaign

Use [the campaign inputs](../examples/campaign-inputs.json). Pick a campaign ID, date window and attribution rule before launch. An example rule is last eligible tagged click within seven days before payment. Store private evidence in your own CRM. Join tagged leads to paid orders using first-party order IDs, deduplicate across videos and channels, and assign each order to at most one campaign under that rule. Keep impressions, traffic, developer installs, leads and accepted payments as separate stages.

Enter upfront production and promotion spend, fully loaded creator and sales labor, and allocated tooling. For each consecutive week enter collected sales excluding indirect taxes, actual refunds, and costs of fulfillment and payment processing. Count confirmed orders and unique first-time customers separately. Repeat orders contribute margin without adding a newly acquired customer. Add attributable net sponsorship, affiliate or platform income once via `other_net_income_usd`. Treat downstream costs consistently there. Use the same currency, attribution policy and observation horizon across comparable campaigns.

Campaign contribution equals collected sales minus refunds and fulfillment costs, plus other net income, minus total campaign cost. Blended CAC divides all campaign spend by attributable new customers. Payback is the first week at or after which cumulative contribution remains nonnegative through the latest supplied week. This assumes all campaign costs are incurred at launch. Later refunds can revise an earlier payback assessment. Modeled break-even orders use realized average margin per order and hold other income fixed.

The example spends $125 upfront. Two $100 orders incur $50 total fulfillment and processing. One buyer is new. The campaign earns $25 after all entered costs, returns 20% of spend, recovers its spend in week two, and has a blended CAC of $125. A campaign with no confirmed new customers reports a null CAC. An observed zero belongs in a field only after the underlying log was checked.

## Evidence and pricing tests

Omitted evidence metadata marks every input as an assumption. Supply both `measured_fields` and `evidence_refs` to promote an input to measured status. Each listed field requires one short internal reference. For example, set `"measured_fields": ["support_minutes"]` and `"evidence_refs": {"support_minutes": "time-log/cohort-A/paid-month-1"}`. For `weeks`, use a reconciled evidence set covering every supplied weekly figure. Partial evidence leaves the field assumed. Reports return the basis and references as entered. Keep account IDs, buyer details, access credentials and raw payment records outside prompts and artifacts.

For an initial price test, use a self-hosted local trial and offer the same supported workflow at the two explicit prices. In comparable, preassigned cohorts track qualified offers, activations, price shown, payments collected, support minutes and first renewal. An explicit decision rule might require at least three paid channels at $29, median monthly support of ten minutes or less, and a measured CAC at or below three months' contribution. At the sample $29 inputs, that CAC ceiling is $56.28. Record unobserved counts as unknown until a source is instrumented. Small counts permit a next-stage pilot decision and have wide uncertainty about market-wide conversion.
