# Relay — Meeting-to-Action Agent

Paste a meeting transcript → GPT-5.6 extracts decisions & action items → you
**review and approve** → Relay files them into Slack, Linear, and Notion.
No copy-paste, and nothing is filed without your confirmation.

**Track:** Work & Productivity · **Built with:** Codex + GPT-5.6

Meeting-notes tools stop at a summary. A human still has to copy action
items into the tracker, ping people on Slack, and write the recap — that's
where decisions quietly die. Relay closes the loop. Every extracted item
keeps its `source_quote` (the exact transcript line it came from), shown
in the review screen so nothing filed is hallucinated.

## Architecture

```
Review UI  →  FastAPI backend
               1. /api/extract → GPT-5.6 turns the transcript into structured JSON
               2. /api/file    → files the approved record directly:
                                 Slack (chat.postMessage), Linear (GraphQL,
                                 one issue per action item), Notion (page create)
```

GPT-5.6 does the one step that needs real reasoning — unstructured text to
structured data. Filing doesn't need an LLM: once approved, the record is
already fully structured, so Relay builds each API call directly instead
of routing it through an agent. (An early version did use an agent + MCP
for filing — see the README's Codex section below for why that changed.)

## Setup

Needs **Python 3.10+**.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (source .venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
copy .env.example .env          # then fill it in
```

| Variable | For | Get it from |
|---|---|---|
| `OPENAI_API_KEY` *or* `OPENROUTER_API_KEY` | extraction | platform.openai.com / openrouter.ai |
| `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`, `SLACK_CHANNEL_ID` | Slack | api.slack.com/apps |
| `LINEAR_API_TOKEN` | Linear | linear.app/settings/api |
| `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID` | Notion | notion.so/my-integrations |

Full click-by-click steps for each token: **[SETUP_TOKENS.md](SETUP_TOKENS.md)**.

**No keys? No problem.** Any tool without tokens runs in demo mode (shows
what it *would* file instead of erroring), and the **"Try demo"** button in
the UI walks the whole paste → review → file flow with zero keys at all.

## Run

```bash
uvicorn api.main:app --port 8000
# open http://127.0.0.1:8000
```

CLI, using the included sample transcript (`samples/standup.txt`):

```bash
python -m relay extract samples/standup.txt -o out.json
python -m relay file samples/standup.json
```

## Project layout

```
relay/            extract.py (GPT-5.6 extraction), file.py (orchestrator),
                   slack_filer.py / linear_filer.py / notion_filer.py (direct filing),
                   mcp_config.py (MCP servers), schema.py, __main__.py (CLI)
api/main.py        FastAPI: /api/extract, /api/file, serves the UI
web/index.html     the review UI (single file, no build step)
samples/           sample transcript + pre-extracted JSON
SETUP_TOKENS.md    step-by-step token setup for every tool
```

## How Codex and GPT-5.6 were used

*(write this part yourself — judges check that it's your own account, not
pasted AI text. Facts from the actual build, to write from:)*

- GPT-5.6 does the extraction step (`relay/extract.py`) — transcript to
  structured JSON.
- Filing originally ran through an OpenAI Agents SDK agent with MCP
  servers. Testing showed models unreliable at multi-step tool calls: one
  run reported success with zero tools called, another completed only 2 of
  5 Linear issues, and no model tested could construct Notion's nested
  block schema correctly.
- Fix: since the approved record is already structured JSON, filing needs
  no LLM judgment — rewrote it as direct API calls
  (`slack_filer.py`, `linear_filer.py`, `notion_filer.py`). Fixed
  reliability and a text-garbling bug in one move.
- Also fixed a false-positive bug where the app reported "filed" without
  checking whether the underlying API call actually succeeded.
- Product decision: review-before-file, with source quotes on every item —
  a trust mechanism, not just a feature.

Grab your `/feedback` Codex Session ID from your build thread for the
Devpost submission form.

## License

MIT — see [LICENSE](LICENSE).
