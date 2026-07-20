"""Filing pipeline: approved extraction JSON -> real side effects via MCP.

An OpenAI Agents SDK agent gets the selected MCP servers attached and is
instructed to file the meeting record:
- Slack:  post the recap + action items to the configured channel.
- Linear: create one issue per action item.
- Notion: create a meeting-notes page.

Tools without configured tokens run in demo mode: we return a preview of
what would have been filed instead of erroring (judge-reproducibility).
"""

import contextlib
import json
import os

from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from agents.items import ToolCallOutputItem

from .extract import OPENROUTER_BASE_URL, get_model
from .linear_filer import file_to_linear
from .mcp_config import build_servers, composio_enabled, configured_tools, missing_tokens
from .notion_filer import file_to_notion
from .schema import MeetingExtraction


def _tool_call_outcome(item: ToolCallOutputItem) -> tuple[bool, str]:
    """Was this MCP tool call actually successful?

    Agents can narrate success even when the underlying tool returned an
    error (seen live: Notion's API rejecting a malformed `parent` argument
    while the model's final summary still claimed the page was created).
    Inspect the raw MCP response instead of trusting the model's words.
    """
    raw = item.raw_item
    output = raw.get("output") if isinstance(raw, dict) else None
    chunks = output if isinstance(output, list) else [output]
    text = " ".join(
        c.get("text", "") for c in chunks if isinstance(c, dict) and "text" in c
    ) or str(output)

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None

    if isinstance(parsed, dict):
        status = parsed.get("status")
        is_error = (
            parsed.get("isError") is True
            or parsed.get("object") == "error"
            or parsed.get("ok") is False
            or (isinstance(status, int) and status >= 400)
            or "error" in parsed
        )
        if is_error:
            return False, parsed.get("message") or text[:300]

    return True, text[:300]


def get_agent_model():
    """Model for the filing agent — OpenRouter (chat-completions) or OpenAI."""
    if os.getenv("OPENROUTER_API_KEY"):
        from openai import AsyncOpenAI

        # tracing uploads need an OpenAI platform key; skip when on OpenRouter
        set_tracing_disabled(True)
        return OpenAIChatCompletionsModel(
            model=get_model(),
            openai_client=AsyncOpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=os.environ["OPENROUTER_API_KEY"],
            ),
        )
    return get_model()

ALL_TOOLS = ["slack", "linear", "notion"]

AGENT_INSTRUCTIONS = """\
You are Relay's filing agent. You receive an approved meeting record and
must file it into the tools listed in the request using your MCP tools.

- Slack: post ONE well-formatted message to the channel given in the
  request (fall back to a channel named #general if none given). Include
  the meeting title, the 2-3 sentence summary, decisions, and the action
  items with owner and due date.
- Linear: create ONE issue per action item. Title = the item title.
  Description = source quote + owner + due date. Map priority
  high/medium/low to urgent/high/medium if the tool supports priority.
  Use the team given in the request, otherwise the first available team.
- Notion: create ONE page titled '<meeting title> — <date>' under the
  parent page given in the request (or the workspace root).
  IMPORTANT (Notion API is strict about shapes -- get these exactly right):
  - `parent` must be an OBJECT: {"page_id": "<the id>"}, never a bare string.
  - Keep `children` to ONE block, type "paragraph", to minimize the chance
    of a malformed block. Put the ENTIRE body — summary, decisions, action
    items with owner/due, open questions — as one paragraph's rich_text,
    using newlines and dashes for structure. Do not use to_do/heading
    blocks; a single paragraph block is far more reliable to construct
    correctly than a multi-block array.
  If a call returns an error, read it, fix the arguments, and retry before
  giving up.

File ONLY into the tools listed in the request — the user explicitly
approved these and nothing else. Do not invent content beyond the record.
When done, report exactly what you created in each tool, with links/IDs
where the tools return them.
"""


def render_preview(tool: str, extraction: dict) -> str:
    """Human-readable preview of what would be filed (demo mode)."""
    m = MeetingExtraction.model_validate(extraction)
    items = "\n".join(
        f"  - {i.title} (owner: {i.owner or 'unassigned'}, due: {i.due or 'n/a'}, {i.priority})"
        for i in m.action_items
    )
    if tool == "slack":
        decisions = "\n".join(f"  - {d.text}" for d in m.decisions) or "  (none)"
        return (
            f"Would post to Slack channel {os.getenv('SLACK_CHANNEL_ID', '#general')}:\n"
            f"*{m.meeting_title}* ({m.date or 'undated'})\n{m.summary}\n"
            f"Decisions:\n{decisions}\nAction items:\n{items or '  (none)'}"
        )
    if tool == "linear":
        return f"Would create {len(m.action_items)} Linear issue(s):\n{items or '  (none)'}"
    if tool == "notion":
        return (
            f"Would create Notion page '{m.meeting_title} — {m.date or 'undated'}' "
            f"with summary, {len(m.decisions)} decision(s), "
            f"{len(m.action_items)} action item(s), {len(m.open_questions)} open question(s)."
        )
    return ""


def build_filing_prompt(extraction: dict, targets: list[str]) -> str:
    m = MeetingExtraction.model_validate(extraction)
    hints = []
    if "slack" in targets and os.getenv("SLACK_CHANNEL_ID"):
        hints.append(f"Slack channel ID: {os.environ['SLACK_CHANNEL_ID']}")
    if "linear" in targets and os.getenv("LINEAR_TEAM_ID"):
        hints.append(f"Linear team ID: {os.environ['LINEAR_TEAM_ID']}")
    if "notion" in targets and os.getenv("NOTION_PARENT_PAGE_ID"):
        hints.append(f"Notion parent page ID: {os.environ['NOTION_PARENT_PAGE_ID']}")
    return (
        f"File this approved meeting record into: {', '.join(targets)}.\n"
        + ("\n".join(hints) + "\n" if hints else "")
        + f"\nMeeting record (JSON):\n{m.model_dump_json(indent=2)}"
    )


async def file_actions(extraction: dict, targets: list[str] | None = None) -> dict:
    """File the approved extraction into the selected tools.

    Returns {tool: {"status": "filed"|"skipped"|"error", "detail": str}}.
    """
    targets = [t for t in (targets or ALL_TOOLS) if t in ALL_TOOLS]
    available = set(configured_tools())
    results: dict[str, dict] = {}

    live = [t for t in targets if t in available]
    for t in targets:
        if t not in available:
            results[t] = {
                "status": "skipped",
                "detail": f"demo mode — missing token(s): {', '.join(missing_tokens(t))}",
                "preview": render_preview(t, extraction),
            }

    # Notion via the direct token: build the exact API payload in Python
    # instead of asking an LLM to construct Notion's strict nested block
    # schema -- no model tested could do that reliably. (Composio-routed
    # Notion still goes through the agent below, since that path exposes a
    # simpler `markdown` tool interface.)
    if "notion" in live and not composio_enabled():
        results["notion"] = await file_to_notion(extraction)
        live = [t for t in live if t != "notion"]

    # Same story for Linear: the agent unreliably completed a full loop of
    # issue-creation calls (stopped partway, or called a read-only tool and
    # reported "filed" regardless). Create every issue directly.
    if "linear" in live and not composio_enabled():
        results["linear"] = await file_to_linear(extraction)
        live = [t for t in live if t != "linear"]

    if not live:
        return results

    async with contextlib.AsyncExitStack() as stack:
        servers = [
            await stack.enter_async_context(s) for s in build_servers(live)
        ]

        agent = Agent(
            name="Relay Filer",
            instructions=AGENT_INSTRUCTIONS,
            model=get_agent_model(),
            mcp_servers=servers,
        )
        try:
            run = await Runner.run(agent, build_filing_prompt(extraction, live))
            outcomes = [
                _tool_call_outcome(item)
                for item in run.new_items
                if isinstance(item, ToolCallOutputItem)
            ]
            successes = [o for o in outcomes if o[0]]
            failures = [o for o in outcomes if not o[0]]

            if not outcomes:
                # The agent returned without ever calling an MCP tool -- a
                # silent no-op some weaker models produce.
                status, detail = "error", (
                    "Agent completed without calling any tools -- nothing "
                    "was actually filed. This is a model reliability issue "
                    "(seen on weaker/free models); try a stronger RELAY_MODEL."
                )
            elif not successes:
                # Every tool call the agent made came back as an error, but
                # the agent may still have (wrongly) claimed success.
                status = "error"
                detail = "All tool calls failed:\n" + "\n".join(
                    f"- {msg}" for _, msg in failures
                )
            else:
                status = "filed"
                detail = f"{run.final_output}\n\n({len(successes)}/{len(outcomes)} tool call(s) succeeded)"

            for t in live:
                results[t] = {"status": status, "detail": detail}
        except Exception as exc:  # report per-tool so partial failures are visible
            for t in live:
                results[t] = {"status": "error", "detail": str(exc)}

    return results
