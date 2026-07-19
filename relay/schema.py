"""Pydantic models for the extraction contract (§5 of the project plan).

This schema is the single contract between extraction, the review UI,
and the filing agent. GPT-5.6 structured output is parsed directly into
MeetingExtraction.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Decision(BaseModel):
    text: str = Field(description="What was decided, one sentence.")
    context: str = Field(description="Supporting quote/excerpt from the transcript.")


class ActionItem(BaseModel):
    title: str = Field(description="Short imperative task, e.g. 'Fix login timeout bug'.")
    owner: Optional[str] = Field(default=None, description="Name of the owner, or null if unassigned.")
    due: Optional[str] = Field(default=None, description="ISO date guess (YYYY-MM-DD) or null.")
    priority: Literal["low", "medium", "high"] = "medium"
    source_quote: str = Field(description="The transcript line this item came from.")


class MeetingExtraction(BaseModel):
    meeting_title: str
    date: Optional[str] = Field(default=None, description="ISO date, best guess or from input.")
    attendees: list[str] = []
    summary: str = Field(description="2-3 sentence recap.")
    decisions: list[Decision] = []
    action_items: list[ActionItem] = []
    open_questions: list[str] = []
