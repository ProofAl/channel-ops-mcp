# Run a first-party growth experiment

Pick one audience, offer and placement. For a product launch, a useful first question is whether channel managers will finish an onboarding call after seeing a working weekly cost-and-receipts report. A later paid-pilot experiment measures collected payments. A lead and a payment represent different decisions.

## Register the decision before sharing a link

The example below sets up a pilot. The thresholds and texts are illustrative. Use your own domain when you generate a link for publication.

```python
from channel_ops.growth import campaign_brief, create_experiment, experiment_report

campaign = "agency-newsletter-pilot"
brief = campaign_brief(
    campaign=campaign,
    destination="https://example.org/creator-pilot",
    source="agency-newsletter",
    medium="referral",
    audience="Editors running small client channels",
    angle="Can one weekly review tell us which campaign covered its production costs?",
    offer="Bring consented, anonymized campaign totals for a 20-minute pilot.",
    cta="Request a pilot session",
)
study = create_experiment(
    campaign, "At least 2 of the first 20 eligible visitors submit a qualified pilot request within 7 days.",
    minimum_sample=20, target_rate=0.10, success_event="lead", window_days=7,
)
print(brief["pitch_draft"])
print(experiment_report(campaign))
```

Review the pitch, publish it through your chosen placement and keep the placement URL in your own distribution log. Generate a distinct campaign slug for each independently evaluated placement. The brief builder keeps unrelated landing-page query parameters and the URL fragment. A generated link does not collect clicks by itself.

## Connect the landing page, CRM and payment records

Run the adapter on the same private machine or service as the ledger. Use a durable writable volume and set `CHANNEL_OPS_DB` to its file path. The default is `~/.local/share/channel-ops-mcp/growth.sqlite3`. Restrict that directory and its backups to the operator. A separate ledger per workspace avoids combining customer data. Public/shared demos should expose the brief builder and synthetic examples only.

1. When a visitor who meets your preregistered eligibility rule lands with a known `utm_campaign`, assign an opaque first-party subject ID and emit `exposed`. Define how you deduplicate consenting visitors before recruitment.
2. Carry the campaign and subject through the opted-in pilot form. Emit `lead` once your CRM confirms the qualification rule.
3. In your private payment handler verify the receipt using your provider’s normal mechanism. Assign a payment to one campaign under a documented attribution rule, such as the first eligible campaign visit within the sales window. Emit `paid` after collection, `refund` on completed refunds, and `expense` for actual campaign costs. Each payment, refund and expense needs its own globally stable event ID. Do not sum multiple campaign reports as unique customers if subjects overlap.
4. Call `experiment_report` for the latest counts. Keep private receipts and identity mappings in the original system. Supply only opaque identifiers and USD cents to this ledger. Record operator labor in the economics model, taking care to avoid double counting any already booked campaign costs.

The following calls illustrate the data contract. Use them against a disposable database for onboarding. Production adapters must supply real evidence, its original timestamp and stable source IDs. Preserve the same subject across events and the same event ID across retries. Prefix IDs by source to avoid collisions. Restrict private adapter calls to your authenticated owner environment.

```python
from channel_ops.growth import record_event

record_event(campaign, "web:visit-72", "exposed", "subj-63", occurred_at="2026-01-10T12:00:00Z")
record_event(campaign, "crm:lead-81", "lead", "subj-63", occurred_at="2026-01-11T13:00:00Z")
record_event(campaign, "payments:r-52", "paid", "subj-63", 2900, occurred_at="2026-01-12T08:05:00Z")
record_event(campaign, "payments:f-10", "refund", "subj-63", 500, occurred_at="2026-01-13T08:05:00Z")
record_event(campaign, "books:x-15", "expense", amount_cents=350, occurred_at="2026-01-13T14:00:00Z")
```

Owners can export a JSON array using `export_events(campaign)`. To restore it, register the same hypothesis on the destination, then call `import_events(campaign, events)`. Each object has exactly these keys:

| Key | Accepted value |
| --- | --- |
| `campaign` | Registered lowercase slug |
| `event_id` | Opaque source-prefixed ID unique across the entire ledger |
| `kind` | `exposed`, `lead`, `paid`, `refund` or `expense` |
| `subject` | Opaque first-party ID, empty for campaign expense |
| `amount_cents` | Positive integer for payments, refunds and costs, zero for the other events |
| `occurred_at` | ISO 8601 timestamp with a timezone, normalized to UTC on import |

The importer commits batches of up to 10,000 events atomically. Replaying identical events is safe. Conflicting content or cross-campaign reuse of the same event ID rejects the batch. Exports include pseudonymous subject IDs and belong in private storage. Public reporting should use aggregate totals.

## Read the result

The scoring cohort is the first `minimum_sample` distinct exposed subjects by earliest exposure time, breaking ties by subject ID. Repeat visits do not enlarge it. For each subject the conversion window begins at first exposure and ends just before that time plus `window_days`. Each subject can count as one conversion. A payment refunded later still counts for a first-payment hypothesis. Refunds reduce reported net cash.

| Decision | Interpretation |
| --- | --- |
| `collecting` | Enrollment is below the target. The conversion rate is provisional. |
| `awaiting_window` | Enrollment is complete. At least one subject still has time to convert. |
| `threshold_met` | All cohort windows have elapsed and the observed fraction met the preregistered target. |
| `below_threshold` | All cohort windows have elapsed and the observed fraction is below target. |

With no eligible exposure the rate is null. Outcomes are descriptive. A single-arm pilot cannot establish causal lift. Historical backfills may change which visitors were first or which conversions qualify. Save a timestamped report and reconcile the source systems before making a spending decision. Cash totals cover every attributed receipt, refund and booked expense in the campaign, including transactions outside the scoring cohort or window. They represent the recorded evidence only.
