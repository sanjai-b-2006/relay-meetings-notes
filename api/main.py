"""FastAPI app: POST /extract, POST /file, and serves the review UI from web/.

Run:  uvicorn api.main:app --reload --port 8000
Open: http://127.0.0.1:8000
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from relay.extract import extract_actions
from relay.file import ALL_TOOLS, file_actions
from relay.mcp_config import configured_tools
from relay.schema import MeetingExtraction

app = FastAPI(title="Relay", description="Meeting-to-action agent")

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


@app.get("/samples/standup.txt")
def sample_transcript() -> FileResponse:
    return FileResponse(ROOT / "samples" / "standup.txt", media_type="text/plain")


class ExtractRequest(BaseModel):
    transcript: str


class FileRequest(BaseModel):
    extraction: MeetingExtraction
    targets: list[str]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status")
def status() -> dict:
    """Which tools have tokens configured (drives the demo-mode badges in the UI)."""
    live = configured_tools()
    return {"tools": {t: ("live" if t in live else "demo") for t in ALL_TOOLS}}


@app.post("/api/extract")
def extract(req: ExtractRequest) -> dict:
    if not req.transcript.strip():
        raise HTTPException(400, "Transcript is empty.")
    try:
        return extract_actions(req.transcript)
    except Exception as exc:
        raise HTTPException(502, f"Extraction failed: {exc}") from exc


@app.post("/api/file")
async def file_endpoint(req: FileRequest) -> dict:
    targets = [t for t in req.targets if t in ALL_TOOLS]
    if not targets:
        raise HTTPException(400, "No valid targets selected.")
    return {"results": await file_actions(req.extraction.model_dump(), targets)}
