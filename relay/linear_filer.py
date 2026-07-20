"""Direct Linear filing -- bypasses the LLM for issue creation.

Live testing showed the filing agent unreliable at completing a full loop
of issue-creation calls: it would create 2 of 5 issues then stop, or in one
run call a read-only tool (e.g. listing teams) and report "filed" without
creating anything at all. Since each action item already has everything
needed (title, owner, due date, priority) as structured JSON, there's
nothing here for an LLM to decide -- create every issue directly via
Linear's GraphQL API.
"""

import os

import httpx

from .schema import MeetingExtraction

LINEAR_API = "https://api.linear.app/graphql"

# Relay's priority -> Linear's numeric scale (0 None, 1 Urgent, 2 High, 3 Normal, 4 Low)
PRIORITY_MAP = {"high": 2, "medium": 3, "low": 4}

TEAMS_QUERY = "query { teams(first: 1) { nodes { id } } }"

CREATE_ISSUE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { id identifier url }
  }
}
"""


async def _graphql(client: httpx.AsyncClient, query: str, variables: dict | None = None) -> dict:
    response = await client.post(
        LINEAR_API,
        headers={
            "Authorization": os.environ["LINEAR_API_TOKEN"],
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise RuntimeError(str(data["errors"]))
    return data["data"]


async def file_to_linear(extraction: dict) -> dict:
    """Create one Linear issue per action item, directly via the API."""
    m = MeetingExtraction.model_validate(extraction)
    if not m.action_items:
        return {"status": "filed", "detail": "No action items to create."}

    async with httpx.AsyncClient(timeout=30) as client:
        team_id = os.getenv("LINEAR_TEAM_ID")
        if not team_id:
            try:
                teams = await _graphql(client, TEAMS_QUERY)
                nodes = teams["teams"]["nodes"]
                if not nodes:
                    return {"status": "error", "detail": "No Linear team available to file into."}
                team_id = nodes[0]["id"]
            except Exception as exc:
                return {"status": "error", "detail": f"Could not resolve a Linear team: {exc}"}

        created, errors = [], []
        for item in m.action_items:
            description = f"Owner: {item.owner or 'unassigned'}\n"
            if item.due:
                description += f"Due: {item.due}\n"
            description += f"\nSource quote: \"{item.source_quote}\"\n\nFiled by Relay from meeting: {m.meeting_title} ({m.date or 'undated'})"
            try:
                result = await _graphql(
                    client,
                    CREATE_ISSUE_MUTATION,
                    {
                        "input": {
                            "teamId": team_id,
                            "title": item.title,
                            "description": description,
                            "priority": PRIORITY_MAP.get(item.priority, 0),
                        }
                    },
                )
                issue_result = result["issueCreate"]
                if issue_result["success"]:
                    created.append(issue_result["issue"]["identifier"])
                else:
                    errors.append(f"{item.title}: creation returned success=false")
            except Exception as exc:
                errors.append(f"{item.title}: {exc}")

    if not created:
        return {"status": "error", "detail": "All issue creations failed:\n" + "\n".join(errors)}

    detail = f"Created {len(created)}/{len(m.action_items)} issues: {', '.join(created)}"
    if errors:
        detail += "\nFailed:\n" + "\n".join(errors)
    return {"status": "filed", "detail": detail}
