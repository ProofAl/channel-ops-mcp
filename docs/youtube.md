# Connect a YouTube channel

Use the owner integration on your own computer in a single-user installation. The private metrics, video titles and drafts returned by these tools are visible to the assistant where you invoke them. The Google authorization code, client secret and refresh token stay on the machine running the local server. Share only aggregate, consented results from pilot channels.

## Enable the APIs and connect

1. In the [Google Cloud console](https://console.cloud.google.com/), select a project and enable **YouTube Data API v3** and **YouTube Analytics API**.
2. In Google Auth Platform, configure the audience and consent screen. For an external app in testing, add your account as a test user. Create an OAuth client with application type **Desktop app**. Save its downloaded JSON outside your checkout.
3. Copy the **Channel ID** from [YouTube advanced settings](https://www.youtube.com/account_advanced) while switched to the intended channel. Use the full value beginning with `UC`.
4. In the same Python environment as the installed plugin, run the command below, substituting your local filename and channel ID. Select the channel owner in the browser and grant the two read scopes. The terminal confirms the channel ID after a live ownership check.

```bash
python -m channel_ops.youtube connect --client-file "/path/to/desktop-client.json" --channel-id "YOUR_UC_CHANNEL_ID"
```

The local browser must be able to reach the Python process on 127.0.0.1. Each server profile serves one owner. Set `CHANNEL_OPS_YOUTUBE_HOME` to a private directory to isolate an additional profile. Set the same value in both the CLI and the local MCP server. Keep owner-enabled servers behind single-user access controls. A shared service requires per-user OAuth and storage isolation.

## First commands in chat

- “Show the title and ID of my connected YouTube channel.”
- “List my five most recent uploads.”
- “Show the daily views, watch minutes, subscribers gained and subscribers lost for my last completed week. Tell me which days Google returned.”
- “Prepare an alternate title for this video and show the before and after. Keep the current language and avoid unsupported claims.”

The Analytics API reports activity when processed by Google. A missing date has unknown activity. Upload dates and titles come from the channel's uploads playlist. Hidden subscriber counts and other absent fields stay absent.

## Publish one approved title

For editing, reconnect with the extra flag. This also requests Google's broader `youtube.force-ssl` scope required by its video metadata endpoint. The chat tool writes a **local title proposal**. Each proposal has an ID, an expiry of seven days and the source video's ETag.

```bash
python -m channel_ops.youtube connect --client-file "/path/to/desktop-client.json" --channel-id "YOUR_UC_CHANNEL_ID" --allow-title-edits
python -m channel_ops.youtube apply-title PROPOSAL_ID
```

Review the channel, video, old title and new title in the terminal. Type the displayed video ID to apply the edit. The CLI reads the video again, checks the original revision and ownership, writes the title and existing mutable snippet fields under an HTTP precondition, then reads the video back. The update requests only the snippet part. If another editor changed the video, prepare a new proposal. After an uncertain network response, check the title in Studio before attempting another edit.

## Disconnect

```bash
python -m channel_ops.youtube disconnect
```

This deletes local credentials and drafts in the selected profile. To revoke the OAuth grant itself, remove the app from [Google account connections](https://myaccount.google.com/connections). Remove the downloaded OAuth client file when you no longer need it. Unix credential files are owner-only. On Windows, use a directory in your private user profile with appropriate filesystem permissions.

## Verification and references

The repository tests exercise the loopback OAuth callback, read-only connection, channel and video ownership, report queries, ETag change refusal, rejection, expiry, mutable fields and read-back with simulated Google responses. Connecting a real channel requires Google consent. OAuth projects serving external users may require Google verification before broad distribution.

- [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Analytics reports query and required read scopes](https://developers.google.com/youtube/analytics/reference/reports/query)
- [Channel reports](https://developers.google.com/youtube/analytics/channel_reports)
- [YouTube video updates, mutable fields and scope](https://developers.google.com/youtube/data/reference/rest/v3/videos/update)
- [YouTube API ETags](https://developers.google.com/youtube/data/getting-started#etags)
