"""Direct Notion filing -- bypasses the LLM agent entirely.

The official Notion MCP server's create-page tool mirrors Notion's raw
nested block API almost 1:1 (parent must be an object, each block is a
tagged union with ~30 possible type keys). Live testing showed no free
model -- not even a 550B one -- could reliably construct that payload; it
kept sending a bare-string `parent` or malformed block arrays.

Since the content itself (title, summary, decisions, action items) is
already fully structured JSON from extraction, there's nothing for an LLM
to decide here. Build the exact Notion API payload in Python instead, so
it's correct by construction regardless of model.
"""

import os

import httpx

from .schema import MeetingExtraction

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1/pages"


def _rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[:2000]}}]


def _heading(text: str, level: int = 2) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": _rich_text(text)}}


def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _todo(text: str) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _rich_text(text), "checked": False},
    }


def build_page_payload(extraction: dict) -> dict:
    m = MeetingExtraction.model_validate(extraction)
    parent_id = os.environ["NOTION_PARENT_PAGE_ID"]

    children: list[dict] = [_heading("Summary"), _paragraph(m.summary)]

    if m.decisions:
        children.append(_heading("Decisions"))
        children += [_bullet(d.text) for d in m.decisions]

    if m.action_items:
        children.append(_heading("Action Items"))
        for item in m.action_items:
            label = f"{item.title} — {item.owner or 'unassigned'}"
            if item.due:
                label += f", due {item.due}"
            label += f" ({item.priority})"
            children.append(_todo(label))

    if m.open_questions:
        children.append(_heading("Open Questions"))
        children += [_bullet(q) for q in m.open_questions]

    return {
        "parent": {"page_id": parent_id},
        "icon": {"emoji": "📅"},
        "properties": {
            "title": {
                "title": _rich_text(f"{m.meeting_title} — {m.date or 'undated'}")
            }
        },
        "children": children[:100],  # Notion's per-request block cap
    }


async def file_to_notion(extraction: dict) -> dict:
    """Create the meeting-notes page directly via the Notion REST API."""
    payload = build_page_payload(extraction)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            NOTION_API,
            headers={
                "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        return {
            "status": "error",
            "detail": f"Notion API {response.status_code}: {response.text[:300]}",
        }

    data = response.json()
    return {"status": "filed", "detail": f"Created Notion page: {data.get('url')}"}
