# Connecting Relay to your tools

Each integration is optional — anything you skip runs in **demo mode**
(shows what it *would* file instead of erroring). Put values in `.env`
and restart the server after each section.

---

## 1. Model provider (for extraction)

**OpenAI:** platform.openai.com → sign in → Billing → add credit (min $5)
→ API keys → create a key → `OPENAI_API_KEY`.

**Or OpenRouter (has free models):** openrouter.ai → sign in → avatar →
Keys → create key → `OPENROUTER_API_KEY`. Set `RELAY_MODEL` to `gpt-5.6`
(needs credit) or a free model like `meta-llama/llama-3.3-70b-instruct:free`.
If both keys are set, OpenRouter wins.

---

## 2. Slack

Goal: `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`, `SLACK_CHANNEL_ID`.

1. api.slack.com/apps → **Create New App** → *From scratch* → name it,
   pick your workspace.
2. **OAuth & Permissions** → Bot Token Scopes → add `chat:write` and
   `channels:read`.
3. **Install to Workspace** → Allow → copy the **Bot User OAuth Token**
   (`xoxb-...`) → `SLACK_BOT_TOKEN`.
4. `SLACK_TEAM_ID`: from the `app.slack.com` URL (`/client/T.../...`, the
   `T...` part).
5. `SLACK_CHANNEL_ID`: right-click the channel → *View channel details*.
6. Invite the bot: type `/invite @Relay` in that channel — without this,
   posting fails with `not_in_channel`.

Test: `python -m relay file samples/standup.json --slack`

---

## 3. Linear

Goal: `LINEAR_API_TOKEN`.

1. linear.app/settings/api → Personal API keys → Create key → copy the
   `lin_api_...` value.

Test: `python -m relay file samples/standup.json --linear`

---

## 4. Notion

Goal: `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID`.

1. notion.so/my-integrations → New integration → Internal, your workspace
   → copy the secret (`ntn_...`) → `NOTION_TOKEN`.
2. Pick a page for recaps to live under, e.g. **Meeting Notes**.
3. On that page: `•••` → Connections → connect your integration — easy
   to miss, but required or the API can't see the page.
4. `NOTION_PARENT_PAGE_ID`: the 32-character ID at the end of the page URL.

Test: `python -m relay file samples/standup.json --notion`

---

## 5. Run it

```bash
uvicorn api.main:app --port 8000     # open http://127.0.0.1:8000
```

Paste a transcript → Extract → review/edit → tick the tools → **Confirm &
file**. Tools with tokens show **live**; the rest show **demo mode**.
