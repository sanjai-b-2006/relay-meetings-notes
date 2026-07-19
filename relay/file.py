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
import os

from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled

from .extract import OPENROUTER_BASE_URL, get_model
from .mcp_config import build_servers, configured_tools, missing_tokens
from .schema import MeetingExtraction


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
  parent page given in the request (or the workspace root). Body: summary,
  decisions, action items (as to-dos), open questions.

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
            for t in live:
                results[t] = {"status": "filed", "detail": run.final_output}
        except Exception as exc:  # report per-tool so partial failures are visible
            for t in live:
                results[t] = {"status": "error", "detail": str(exc)}

    return results
