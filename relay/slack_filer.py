"""Direct Slack filing -- bypasses the LLM for message composition.

Live testing showed the filing agent's Slack message occasionally garbled
with stray non-English tokens (a free-model quality artifact, not a
formatting choice). Since the recap is fully determined by the extraction
JSON, there's nothing for an LLM to decide here either -- build the exact
Slack message text in Python and post it directly.
"""

import os

import httpx

from .schema import MeetingExtraction

SLACK_POST_MESSAGE = "https://slack.com/api/chat.postMessage"


def build_message(extraction: dict) -> str:
    m = MeetingExtraction.model_validate(extraction)

    lines = [f":calendar: *{m.meeting_title}* ({m.date or 'undated'})", "", m.summary]

    if m.decisions:
        lines += ["", "*Decisions*"]
        lines += [f"• {d.text}" for d in m.decisions]

    if m.action_items:
        lines += ["", "*Action Items*"]
        for item in m.action_items:
            due = f", due {item.due}" if item.due else ""
            lines.append(f"• *{item.title}* — {item.owner or 'unassigned'}{due} ({item.priority})")

    if m.open_questions:
        lines += ["", "*Open Questions*"]
        lines += [f"• {q}" for q in m.open_questions]

    return "\n".join(lines)


async def file_to_slack(extraction: dict) -> dict:
    """Post the meeting recap directly via the Slack Web API."""
    text = build_message(extraction)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            SLACK_POST_MESSAGE,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_CHANNEL_ID"],
                "text": text,
            },
        )

    if response.status_code >= 400:
        return {"status": "error", "detail": f"Slack API HTTP {response.status_code}: {response.text[:300]}"}

    data = response.json()
    if not data.get("ok"):
        return {"status": "error", "detail": f"Slack API error: {data.get('error')}"}

    return {
        "status": "filed",
        "detail": f"Posted to Slack channel {data.get('channel')} (ts {data.get('ts')})",
    }
