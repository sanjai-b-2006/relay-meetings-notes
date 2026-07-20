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
  confirm                 2. /api/file    → direct filing (no LLM needed --
                                             the record is already structured)
                                            ├─ Slack   chat.postMessage
                                            ├─ Linear  GraphQL issueCreate (one per action item)
                                            └─ Notion  REST pages.create
```

Extraction is the one place GPT-5.6 genuinely needs to reason (unstructured
transcript → structured JSON). Filing doesn't -- the record is already
fully structured by the time it's approved, so there's nothing left for an
LLM to decide. Early versions routed filing through an OpenAI Agents SDK
agent with MCP servers attached; live testing showed models unreliable at
completing multi-step tool-call loops (partial Linear runs, malformed
Notion block JSON, garbled Slack text). Swapping to direct API calls fixed
all three, and it's the more honest design anyway. The agent+MCP path is
still available for the optional Composio-routed connection (see
`relay/mcp_config.py`, `relay/file.py`).

## Setup

Requirements: **Python 3.10+**, **Node.js** (the MCP servers run via `npx`).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # then edit .env
```

Fill in `.env` — **[SETUP_TOKENS.md](SETUP_TOKENS.md) has click-by-click
instructions for every token below.**

| Variable | Needed for | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` *or* `OPENROUTER_API_KEY` | extraction + filing agent | platform.openai.com / openrouter.ai (OpenRouter has free models; see `RELAY_MODEL`) |
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

## Connecting Codex to this project (Slack/Linear/Notion via Composio)

If you're doing your Build Week session in **Codex** and want it to be able
to call Slack/Linear/Notion directly (e.g. to test filing, or to extend
`relay/mcp_config.py`), connect Composio's managed MCP endpoint there too.

**CLI (recommended — handles auth for you):**

```bash
codex mcp add https://connect.composio.dev/mcp
```

This opens a browser to authorize Codex against your Composio account. Verify
with `codex mcp list` (or `/mcp` inside a Codex session) — it should list
`composio` with Slack/Linear/Notion tools available.

**Manual config**, if you'd rather not do the browser flow — edit
`~/.codex/config.toml`:

```toml
[mcp_servers.composio]
url = "https://connect.composio.dev/mcp"
http_headers = { "x-consumer-api-key" = "ak_..." }   # your Composio API key
```

**Note:** this is separate from Relay's own runtime config. The app itself
(`uvicorn`/`python -m relay`) reads `COMPOSIO_API_KEY` from **this project's
`.env`**, not from Codex's or Claude's MCP settings — see the Composio
section of [SETUP_TOKENS.md](SETUP_TOKENS.md#2-composio).

## Project layout

```
relay/            core package
  extract.py      GPT-5.6 structured extraction (chat.completions.parse → pydantic)
  file.py         orchestrates filing + demo-mode previews; agent/MCP path for Composio
  slack_filer.py  direct Slack filing (chat.postMessage)
  linear_filer.py direct Linear filing (GraphQL issueCreate, one call per action item)
  notion_filer.py direct Notion filing (REST pages.create)
  mcp_config.py   MCP stdio server + Composio HTTP server definitions
  schema.py       the extraction contract (pydantic)
  __main__.py     CLI (extract / file)
api/main.py       FastAPI: /api/extract, /api/file, serves the UI
web/index.html    3-step review UI (paste → review/edit → confirmation)
samples/          sample transcript + pre-extracted JSON for judges
```

## How Codex and GPT-5.6 were used

<!-- WRITE THIS SECTION YOURSELF, IN YOUR OWN WORDS, before submitting.
     Judges read this and it's part of how they score Technological
     Implementation and Quality of the Idea -- an AI-generated paragraph
     pasted in as-is is exactly what the rules say not to do.

     Below are the real, concrete facts from the actual build, as talking
     points / a memory-jogger -- turn the ones that are true for you into
     your own sentences, cut what isn't relevant, add what's missing. Also
     grab your /feedback Session ID from your primary Codex thread and put
     it in the Devpost submission form.

     Facts from the build, for reference:
     - GPT-5.6 (via OpenAI or OpenRouter, see RELAY_MODEL) does the one
       genuinely hard reasoning step: unstructured transcript -> structured
       JSON (decisions, action items with owner/due/priority, source
       quotes) in relay/extract.py.
     - First design used an OpenAI Agents SDK agent with MCP servers
       (Slack/Linear/Notion) for filing too. Live testing surfaced real
       reliability problems: the agent sometimes returned "success" having
       called zero tools, sometimes completed only 2 of 5 Linear issues,
       and Notion's strict nested block schema was never constructed
       correctly by any model tried (including a 550B one).
     - Key engineering decision: since the approved record is already
       fully structured JSON, filing doesn't need an LLM's judgment at
       all -- rewrote Slack/Linear/Notion filing as direct API calls
       (slack_filer.py, linear_filer.py, notion_filer.py) that build the
       exact request from the data. This fixed reliability AND a garbled/
       mixed-language text quality bug in one move, and made filing
       deterministic regardless of model tier.
     - Also added: a status-verification fix so the app checks actual API
       responses instead of trusting the agent's claimed success (caught a
       real false-positive bug live: "filed" was reported when nothing had
       actually been created).
     - Product decision: review-before-file UI (nothing files without
       explicit confirmation, every item shows its source_quote) -- a
       deliberate trust design, not just a feature.
     - Demo-mode fallback (tools without configured tokens show a preview
       of what would be filed) so judges can exercise the whole pipeline
       without setting up accounts. -->

## License

MIT — see [LICENSE](LICENSE).
