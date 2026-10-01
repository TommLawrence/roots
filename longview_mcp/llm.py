"""Open-weights LLM client.

Default: Ollama (OpenAI-compatible endpoint on localhost) running
qwen2.5:3b-instruct-q4_K_M - ~2 GB RAM, sized for an 8 GB laptop.

Hard rules baked into the prompt:
  - only reorganise the cited facts provided; never invent a claim or number
  - plain language, a guardian with no education jargon can read it
  - a conversation opener for the teacher, never prescriptive, never a verdict
Returns None on any failure so callers can fall back to the template drafter.
"""

import os

import httpx


def _base_url() -> str:
    return os.environ.get("LONGVIEW_LLM_BASE_URL", "http://localhost:11434/v1")


def _model() -> str:
    return os.environ.get("LONGVIEW_MODEL", "qwen2.5:3b-instruct-q4_K_M")


SYSTEM_PROMPT = (
    "You write short plain-language learner updates for a teacher to read to a guardian. "
    "RULES: use ONLY the numbers and facts in the provided FACTS JSON - never invent or "
    "round any number, never add a claim that is not listed. "
    "Never suggest a school track, subject path, or career. Never rank the child. "
    "Frame every point as something to discuss with the teacher. "
    "Keep it under 180 words. Simple sentences."
)


def chat(messages: list[dict], timeout: float = 90.0) -> str | None:
    try:
        resp = httpx.post(
            f"{_base_url()}/chat/completions",
            json={"model": _model(), "messages": messages, "temperature": 0.2},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def summarize(facts: dict) -> str | None:
    """Return a draft summary from cited facts, or None to use the template."""
    import json as _json

    compact = {
        "learner": facts["profile"]["learner"]["name"],
        "profile_entries": [
            {"kind": e["kind"], "claim": e["claim"],
             "evidence": [{"term": ev["term"], "skill": ev["skill"],
                           "value": ev["value"], "source": ev["source_ref"]}
                          for ev in e["evidence"]]}
            for e in facts["profile"]["profile_entries"]
        ],
        "findings": [
            {k: v for k, v in f.items()
             if k in ("pattern_type", "skill", "rationale")}
            for f in facts["findings"]
        ],
        "allowed_numbers": facts["allowed_numbers"],
    }
    return chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"FACTS JSON:\n{_json.dumps(compact, indent=1)}"},
    ])
