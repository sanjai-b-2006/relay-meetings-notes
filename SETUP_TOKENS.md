# Connecting Relay to your tools — step by step

Every integration is optional: anything you skip runs in **demo mode**
(Relay shows what it *would* have filed). Node.js must be installed —
the MCP servers are launched with `npx`.

After each section, put the values into `.env` and restart the server.

---

## 1. Model provider (required for live extraction)

### Option A — OpenAI platform
1. Go to <https://platform.openai.com> → sign in.
2. Settings → **Billing** → add a payment method / credit (min $5).
3. **API keys** → *Create new secret key* → copy into `OPENAI_API_KEY`.

### Option B — OpenRouter (free models available)
1. Go to <https://openrouter.ai> → sign in (Google/GitHub works).
2. Click your avatar → **Keys** → *Create Key* → copy the `sk-or-...`
   value into `OPENROUTER_API_KEY`.
3. Pick a model in `RELAY_MODEL`:
   - `gpt-5.6` (auto-prefixed to `openai/gpt-5.6`; needs OpenRouter credit), or
   - a free model, e.g. `meta-llama/llama-3.3-70b-instruct:free`
     (browse <https://openrouter.ai/models?max_price=0>).
4. Free models are rate-limited and weaker at tool calling; for the demo
   video, a paid model gives crisper extractions.

If both keys are set, OpenRouter wins.

---

## 2. Slack

Goal: `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`, `SLACK_CHANNEL_ID`.

1. Go to <https://api.slack.com/apps> → **Create New App** → *From scratch*.
   Name it `Relay`, pick your workspace.
2. In the left sidebar: **OAuth & Permissions** → scroll to
   *Scopes → Bot Token Scopes* → add:
   - `chat:write`   (post messages)
   - `channels:read` (list channels)
3. Scroll up → **Install to Workspace** → Allow.
4. Copy the **Bot User OAuth Token** (`xoxb-...`) → `SLACK_BOT_TOKEN`.
5. `SLACK_TEAM_ID`: open Slack in a browser (`app.slack.com`) — the URL
   contains `/client/T.../...`; the `T...` part is the team ID.
   (Or: workspace name → *About this workspace*.)
6. `SLACK_CHANNEL_ID`: right-click the target channel → *View channel
   details* → the `C...` ID is at the bottom of the About tab.
7. **Important:** invite the bot to that channel — type `/invite @Relay`
   in the channel. Without this, posting fails with `not_in_channel`.

Quick test: `python -m relay file samples/standup.json --slack`
→ a formatted recap should appear in the channel.

---

## 3. Linear

Goal: `LINEAR_API_TOKEN` (and optionally `LINEAR_TEAM_ID`).

1. Go to <https://linear.app/settings/api> (Settings → API).
2. Under **Personal API keys** → *Create key* → name it `Relay` →
   copy the `lin_api_...` value into `LINEAR_API_TOKEN`.
3. Optional: `LINEAR_TEAM_ID` — the agent will use your first team if
   unset. To pin it: Settings → Teams → open your team; or copy the
   3-letter team key (e.g. `ENG`) from any issue id like `ENG-123` and
   let the agent resolve it.

Quick test: `python -m relay file samples/standup.json --linear`
→ one issue per action item appears in your team.

---

## 4. Notion

Goal: `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID`.

1. Go to <https://www.notion.so/my-integrations> → **New integration**.
   - Name: `Relay`; Type: *Internal*; workspace: yours.
   - Capabilities: Read + Insert + Update content.
2. Copy the **Internal Integration Secret** (`ntn_...`) → `NOTION_TOKEN`.
3. In Notion, create (or pick) a page where recaps should live, e.g.
   **Meeting Notes**.
4. On that page: `•••` menu (top-right) → **Connections** →
   *Connect to* → pick `Relay`. ← the step everyone forgets; without it
   the API cannot see the page at all.
5. `NOTION_PARENT_PAGE_ID`: copy the page URL — the 32-hex-character tail
   is the ID, e.g. `notion.so/Meeting-Notes-1a2b3c...` →
   `1a2b3c...` (dashes optional).

Quick test: `python -m relay file samples/standup.json --notion`
→ a new meeting-notes page appears under your parent page.

---

## 5. Everything at once

```bash
uvicorn api.main:app --port 8000     # open http://127.0.0.1:8000
```

Paste a transcript → Extract → review/edit items → tick the tools →
**Confirm & file**. Tools with tokens show a green **live** badge; the
rest show **demo mode**.
