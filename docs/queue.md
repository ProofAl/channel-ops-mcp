# Export a video brief to your content queue

`export_queue_draft` returns a UTF-8 CSV document containing a header and one draft. Use a target alias you have registered in your own system. The receiver validates that alias, the content, evidence and destination under its own editorial policy. The export is a local handoff. A receiving system must explicitly import it.

```python
from pathlib import Path
from channel_ops.queue_export import export_queue_draft

draft = export_queue_draft(
    content_id="weekly-review-a",
    channel="youtube_shorts",
    title="Can we prepare a weekly channel review in ten minutes?",
    description="Follow one review from the video report to the next experiment.",
    target_id="demo-channel",
    media_ref="review-a.mp4",
    evidence_ref="research/demo-run-01",
    link_url="https://example.org/creator-pilot",
    utm_campaign="weekly-review",
)
with Path("weekly-review.csv").open("w", encoding="utf-8", newline="") as out:
    out.write(draft)
```

| Columns | Exported value |
| --- | --- |
| `content_id`, `channel` | One stable variant ID and either `youtube` or `youtube_shorts` |
| `scheduled_at`, `published_at`, `remote_post_id`, `last_error` | Empty |
| `status`, `origin`, `visibility` | `draft`, `control`, `private` |
| `pillar`, `text` | Optional editorial theme and a quoted cell with the title on its first line and the description below |
| `link_url`, `utm_campaign` | Optional destination and campaign for attribution |
| `target_id`, `media_ref`, `evidence_ref` | Your channel alias, opaque asset name and a reference to evidence for the brief |

Give each variant its own stable `content_id` and use it for deduplication on import. Receivers following this attribution convention append `utm_source=<channel>`, `utm_medium=organic_social`, `utm_campaign=<campaign>` and `utm_content=<content_id>` to the destination when rendering the draft. The CSV carries the destination exactly as supplied. Unspecified campaigns default to `organic` when the receiver constructs that link.

For spreadsheet use, formula prefixes in user-controlled cells are rejected and quotes, commas and multiline descriptions are CSV-escaped. Keep internal drafts and evidence references in a destination with the intended audience.
