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

GPT-5.6 is the model doing the actual work at runtime: it's what turns a
messy, unstructured meeting transcript into structured JSON — decisions,
action items with owner/due date/priority, and open questions, each one
tied back to the exact line it came from (`relay/extract.py`).

The filing pipeline went through a real redesign during development.
The first version routed Slack/Linear/Notion filing through an LLM agent
over MCP, on the assumption that an agent should own every side effect.
Testing that assumption exposed real reliability problems: a run could
report "filed" after calling zero tools, an issue-creation loop could
stop partway through, and Notion's strict nested block schema was never
constructed correctly. The fix was a design change, not a bigger model:
since the approved record is already fully structured JSON by the time
it's filed, there's no judgment left for an LLM to make — so filing was
rewritten as direct, deterministic API calls
(`slack_filer.py`, `linear_filer.py`, `notion_filer.py`). That fixed the
reliability problems and a text-quality bug in one move, and made the
whole pipeline correct regardless of which model is configured.

Codex did a focused pass on the review/results screen (`web/index.html`)
and the filer response shape: it added structured `url`/`urls` fields to
the three filing modules, then used them to render real clickable links
and a per-tool progress indicator on the confirmation screen, instead of
the plain-text result block that was there before.

The review-before-file design — nothing is sent anywhere without explicit
confirmation, and every item shows its source quote — was a deliberate
trust decision from the start: the value of automating meeting follow-up
disappears fast if people can't trust what got filed.

`/feedback` Codex Session ID: _paste yours here before submitting._

## License

MIT — see [LICENSE](LICENSE).
