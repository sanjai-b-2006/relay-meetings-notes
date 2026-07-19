"""MCP server definitions for Slack, Linear, and Notion.

Two connection modes, auto-detected from the environment:

1. Composio (recommended if you don't want to hunt for per-service API
   keys): set COMPOSIO_API_KEY (from dashboard.composio.dev -> Settings ->
   API Keys). Connect Slack/Linear/Notion via OAuth login in the dashboard.
   No URL to find -- Relay talks to Composio's fixed managed endpoint
   (COMPOSIO_CONNECT_URL) unless COMPOSIO_MCP_URL overrides it.

2. Direct per-service stdio servers (the original approach): each tool
   needs its own token(s), documented in .env.example / SETUP_TOKENS.md.
   Community/official servers launched as npx subprocesses.

If a tool isn't configured either way, Relay runs in "demo mode" for it:
instead of filing, it prints/returns what WOULD have been filed. This lets
judges see the full pipeline without setting up every workspace.
"""

import json
import os
import sys

from agents.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHttp

# npx lives at npx.cmd on Windows
NPX = "npx.cmd" if sys.platform == "win32" else "npx"

TOOL_TOKENS: dict[str, list[str]] = {
    "slack": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    "linear": ["LINEAR_API_TOKEN"],
    "notion": ["NOTION_TOKEN"],
}


# Composio's fixed managed MCP endpoint -- works for any account, no
# per-project "create an MCP server" step needed. Auth is one header.
COMPOSIO_CONNECT_URL = "https://connect.composio.dev/mcp"


def composio_enabled() -> bool:
    return bool(os.getenv("COMPOSIO_API_KEY"))


def configured_tools() -> list[str]:
    """Tools available to file into, right now."""
    if composio_enabled():
        # Which apps you actually connected in the Composio dashboard.
        declared = os.getenv("COMPOSIO_TOOLS", "slack,linear,notion")
        return [t.strip() for t in declared.split(",") if t.strip() in TOOL_TOKENS]
    return [
        tool
        for tool, tokens in TOOL_TOKENS.items()
        if all(os.getenv(t) for t in tokens)
    ]


def missing_tokens(tool: str) -> list[str]:
    if composio_enabled():
        return ["COMPOSIO_TOOLS (declare this tool)"]
    return [t for t in TOOL_TOKENS[tool] if not os.getenv(t)]


def build_composio_server() -> MCPServerStreamableHttp:
    url = os.getenv("COMPOSIO_MCP_URL", COMPOSIO_CONNECT_URL)
    headers = {"x-consumer-api-key": os.environ["COMPOSIO_API_KEY"]}
    return MCPServerStreamableHttp(
        name="composio",
        params={"url": url, "headers": headers},
        cache_tools_list=True,
        client_session_timeout_seconds=60,
    )


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
            client_session_timeout_seconds=60,
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
            client_session_timeout_seconds=60,
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
            client_session_timeout_seconds=60,
        )
    raise ValueError(f"Unknown tool: {tool}")


def build_servers(live: list[str]) -> list[MCPServer]:
    """Build the MCP server(s) needed to file into `live` tools.

    Composio mode: one shared HTTP server covers every tool. Direct mode:
    one stdio subprocess per tool.
    """
    if composio_enabled():
        return [build_composio_server()] if live else []
    return [build_server(t) for t in live]
