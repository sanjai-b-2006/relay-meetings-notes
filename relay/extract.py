"""Transcript -> structured extraction.

Provider is auto-detected:
- OPENROUTER_API_KEY set  -> OpenRouter (OpenAI-compatible, openrouter.ai)
- otherwise               -> OpenAI platform (OPENAI_API_KEY)

RELAY_MODEL picks the model. On OpenRouter, bare OpenAI model names are
auto-prefixed ("gpt-5.6" -> "openai/gpt-5.6"); set a full id like
"meta-llama/llama-3.3-70b-instruct:free" to use anything else.
"""

import json
import os
import re
import time

from openai import OpenAI

from .schema import MeetingExtraction

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_model() -> str:
    model = os.getenv("RELAY_MODEL", "gpt-5.6")
    if os.getenv("OPENROUTER_API_KEY") and "/" not in model:
        model = f"openai/{model}"
    return model


def get_client() -> OpenAI:
    if os.getenv("OPENROUTER_API_KEY"):
        return OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
    return OpenAI()


SYSTEM_PROMPT = """\
You are Relay, an assistant that turns raw meeting transcripts into a
structured record of what happened. Extract:

- meeting_title: short descriptive title (invent one if not stated).
- date: ISO date if stated or clearly inferable, else null. Today's date
  may be given in the transcript header.
- attendees: every distinct speaker or named participant.
- summary: a 2-3 sentence recap a person who missed the meeting would want.
- decisions: things the group DECIDED (not proposals still under discussion).
  Include the supporting transcript excerpt as `context`.
- action_items: concrete tasks someone should do. For each:
  - title: short imperative phrasing ("Fix login timeout bug").
  - owner: the person responsible if identifiable, else null. Use the name
    as spoken in the transcript.
  - due: ISO date if a deadline was stated or clearly implied ("by Friday"
    -> the next Friday relative to the meeting date), else null.
  - priority: high if urgent/blocking or explicitly urgent, low if clearly
    minor, otherwise medium.
  - source_quote: the exact transcript line(s) that justify this item.
- open_questions: unresolved questions raised but not answered.

Only extract what is actually supported by the transcript. Never invent
owners, dates, or tasks. source_quote must be copied from the transcript,
not paraphrased.
"""

JSON_FALLBACK_SUFFIX = (
    "\nRespond with ONLY a JSON object matching this schema, no prose, "
    "no markdown fences:\n" + json.dumps(MeetingExtraction.model_json_schema())
)


def _extract_json_fallback(client: OpenAI, model: str, transcript: str) -> dict:
    """Plain JSON-mode path for models without structured-output support.

    Free-tier models occasionally return empty or malformed output, so
    retry a few times before giving up.
    """
    last_error: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(10)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + JSON_FALLBACK_SUFFIX},
                    {"role": "user", "content": transcript},
                ],
            )
            text = (completion.choices[0].message.content or "").strip()
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
            if not text:
                raise ValueError("model returned an empty response")
            return MeetingExtraction.model_validate_json(text).model_dump()
        except Exception as exc:
            last_error = exc
    raise last_error


def extract_actions(transcript: str) -> dict:
    """Run structured extraction over a raw transcript."""
    client = get_client()
    model = get_model()
    try:
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            response_format=MeetingExtraction,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("model returned no parsed output")
        return parsed.model_dump()
    except Exception:
        # some providers/models don't support json_schema response_format
        return _extract_json_fallback(client, model, transcript)
