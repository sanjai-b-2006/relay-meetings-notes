"""Definitions of the three MCP stdio servers (Slack, Linear, Notion).

Each tool is described by:
- the env tokens it needs (documented in .env.example),
- a factory that builds an MCPServerStdio for the OpenAI Agents SDK.

If a tool's tokens are missing, Relay runs in "demo mode" for that tool:
instead of filing, it prints/returns what WOULD have been filed. This lets
judges see the full pipeline without setting up every workspace.

The server packages below are community/official stdio servers launched via
npx (Node.js required). Swap the commands here if you prefer different ones.
"""

import json
import os
import sys

from agents.mcp import MCPServerStdio

# npx lives at npx.cmd on Windows
NPX = "npx.cmd" if sys.platform == "win32" else "npx"

TOOL_TOKENS: dict[str, list[str]] = {
    "slack": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    "linear": ["LINEAR_API_TOKEN"],
    "notion": ["NOTION_TOKEN"],
}


def configured_tools() -> list[str]:
    """Tools whose required tokens are all present in the environment."""
    return [
        tool
        for tool, tokens in TOOL_TOKENS.items()
        if all(os.getenv(t) for t in tokens)
    ]


def missing_tokens(tool: str) -> list[str]:
    return [t for t in TOOL_TOKENS[tool] if not os.getenv(t)]


def build_server(tool: str) -> MCPServerStdio:
    """Build the MCP stdio server subprocess definition for one tool."""
    if tool == "slack":
        return MCPServerStdio(
            name="slack",
            params={
                "command": NPX,
                "args": ["-y", "@modelcontextprotocol/server-slack"],
                "env": {
                    "SLACK_BOT_TOKEN": os.environ["SLACK_BOT_TOKEN"],
                    "SLACK_TEAM_ID": os.environ["SLACK_TEAM_ID"],
                },
            },
            cache_tools_list=True,
        )
    if tool == "linear":
        return MCPServerStdio(
            name="linear",
            params={
                "command": NPX,
                "args": ["-y", "@tacticlaunch/mcp-linear"],
                "env": {"LINEAR_API_TOKEN": os.environ["LINEAR_API_TOKEN"]},
            },
            cache_tools_list=True,
        )
    if tool == "notion":
        return MCPServerStdio(
            name="notion",
            params={
                "command": NPX,
                "args": ["-y", "@notionhq/notion-mcp-server"],
                "env": {
                    "OPENAPI_MCP_HEADERS": json.dumps(
                        {
                            "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                            "Notion-Version": "2022-06-28",
                        }
                    )
                },
            },
            cache_tools_list=True,
        )
    raise ValueError(f"Unknown tool: {tool}")
