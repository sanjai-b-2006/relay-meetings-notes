"""CLI entry point.

    python -m relay extract samples/standup.txt [-o samples/standup.json]
    python -m relay file samples/standup.json [--slack] [--linear] [--notion]

With no tool flags, `file` targets all three (tools without tokens run in
demo mode and print what would be filed).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Windows consoles default to cp1252, which chokes on emoji in agent output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def cmd_extract(args: argparse.Namespace) -> None:
    from .extract import extract_actions

    transcript = Path(args.transcript).read_text(encoding="utf-8")
    result = extract_actions(transcript)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote extraction to {args.output}")
    else:
        print(output)


def cmd_file(args: argparse.Namespace) -> None:
    from .file import ALL_TOOLS, file_actions

    extraction = json.loads(Path(args.extraction).read_text(encoding="utf-8"))
    targets = [t for t in ALL_TOOLS if getattr(args, t)] or None
    results = asyncio.run(file_actions(extraction, targets))
    for tool, result in results.items():
        print(f"\n=== {tool}: {result['status']} ===")
        print(result.get("preview") or result["detail"])
    if any(r["status"] == "error" for r in results.values()):
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="relay", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract structured actions from a transcript")
    p_extract.add_argument("transcript", help="Path to a transcript .txt file")
    p_extract.add_argument("-o", "--output", help="Write JSON here instead of stdout")
    p_extract.set_defaults(func=cmd_extract)

    p_file = sub.add_parser("file", help="File an approved extraction JSON into tools")
    p_file.add_argument("extraction", help="Path to extraction .json file")
    p_file.add_argument("--slack", action="store_true")
    p_file.add_argument("--linear", action="store_true")
    p_file.add_argument("--notion", action="store_true")
    p_file.set_defaults(func=cmd_file)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
