# Relay — Meeting-to-Action Agent

Paste a meeting transcript → Relay extracts decisions & action items with GPT-5.6 →
you **review and approve** → an agent *files* them into Slack, Linear, and Notion via MCP.
No copy-paste.

**Track:** Work & Productivity · **Built with:** Codex + GPT-5.6 (OpenAI Agents SDK, native MCP)

## Why it's not just another summarizer

Meeting-notes tools stop at a summary. A human still copies action items into the
issue tracker, pings owners on Slack, and writes the recap. That manual triage is
where decisions quietly die. Relay closes the loop: tickets get created, the channel
gets pinged, the recap gets written — with a **review-before-file** step so nothing
wrong is ever filed automatically.

Every extracted item carries its `source_quote` — the exact transcript line it came
from — shown in the review UI so you can verify nothing was hallucinated.

## Architecture

```
Frontend (review UI)  →  FastAPI backend
  paste / review /        1. /api/extract → GPT-5.6 structured extraction
  confirm                 2. /api/file    → OpenAI Agents SDK agent
                                            with MCP stdio servers attached
                                            ├─ Slack MCP   (post recap)
                                            ├─ Linear MCP  (create issues)
                                            └─ Notion MCP  (write notes page)
```

## Setup

Requirements: **Python 3.10+**, **Node.js** (the MCP servers run via `npx`).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # then edit .env
```

Fill in `.env`:

| Variable | Needed for | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | extraction + filing agent (required) | platform.openai.com |
| `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`, `SLACK_CHANNEL_ID` | Slack filing | api.slack.com/apps (bot token needs `chat:write`, `channels:read`) |
| `LINEAR_API_TOKEN`, `LINEAR_TEAM_ID` | Linear filing | linear.app/settings/api |
| `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID` | Notion filing | notion.so/my-integrations (share the parent page with the integration) |

**Demo mode (no tokens needed):** any tool whose tokens are missing is *not* an
error — Relay shows exactly what it *would* have filed. And the **"Try demo (no
API key)"** button in the UI loads a pre-extracted sample record straight into
the review screen, so the entire paste → review → file flow can be tested with
**zero** keys of any kind. With just an `OPENAI_API_KEY`, live GPT-5.6
extraction works too.

## Run

**Web app (main experience):**

```bash
uvicorn api.main:app --port 8000
# open http://127.0.0.1:8000  →  "Load sample transcript" → Extract → Review → Confirm
```

**CLI:**

```bash
# transcript → structured JSON (uses GPT-5.6)
python -m relay extract samples/standup.txt -o out.json

# approved JSON → filed into tools (or demo-mode previews)
python -m relay file samples/standup.json --slack --linear --notion

# no flags = all three tools
python -m relay file samples/standup.json
```

`samples/standup.json` is a pre-extracted record, so the filing pipeline can be
tested in under a minute without any API keys.

## Project layout

```
relay/            core package
  extract.py      GPT-5.6 structured extraction (responses.parse → pydantic)
  file.py         OpenAI Agents SDK filing agent + demo-mode previews
  mcp_config.py   the 3 MCP stdio server definitions
  schema.py       the extraction contract (pydantic)
  __main__.py     CLI (extract / file)
api/main.py       FastAPI: /api/extract, /api/file, serves the UI
web/index.html    3-step review UI (paste → review/edit → confirmation)
samples/          sample transcript + pre-extracted JSON for judges
```

## How Codex and GPT-5.6 were used

<!-- FILL THIS IN YOURSELF before submitting — judges read it and score on it.
     Describe honestly:
     - which parts you built in Codex sessions (cite concrete examples: wiring
       the MCP servers, debugging the agent loop, building the review UI, ...)
     - where GPT-5.6 is used at runtime (extraction + the filing agent — see
       RELAY_MODEL in .env) and where you used GPT-5.6 in Codex during the build
     - key product/engineering decisions you made and why (e.g. the
       review-before-file design, stdio MCP servers over OAuth for
       reproducibility, demo mode for judges)
     Remember to grab your /feedback Session ID from your primary Codex thread
     and put it in the Devpost submission form. -->

- **GPT-5.6 at runtime:** powers both stages — the structured transcript
  extraction (`relay/extract.py`) and the MCP filing agent (`relay/file.py`).
- **Codex during the build:** _describe your sessions here._

## License

MIT — see [LICENSE](LICENSE).
