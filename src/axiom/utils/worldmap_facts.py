"""
Deterministic extraction of "ExamplePerson hard facts" from user text.

Conservative by design:
- Only emits ops when the value is directly present as an exact substring capture.
- Confidence is only 0.95 for exact matches; otherwise emits nothing.

Returned op shape:
  {
    "op": "replace" | "add",
    "path": "/wife_name" | "/birth_place" | "/kids" | ...,
    "value": <jsonable>,
    "confidence": 0.95,
    "extracted_span": <exact substring used for the value OR primary span>,
    "extracted_spans": [<optional additional spans>],
  }
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


_CONF_EXACT = 0.95


def _cap_span(text: str, m: re.Match, group: int | str) -> str:
    try:
        s, e = m.span(group)
        return text[s:e]
    except Exception:
        return ""


def extract_kurt_hard_facts(user_text: str) -> list[dict]:
    text = (user_text or "")
    if not text.strip():
        return []

    ops: list[dict] = []

    # Reject hedged/uncertain phrasing (conservative).
    low = text.lower()
    if any(h in low for h in ("i think", "maybe", "probably", "not sure", "might be", "i guess")):
        return []

    # 1) "ExamplePerson's wife's name is X" (also allow "ExamplePerson’s")
    wife_pat = re.compile(
        r"\bKurt(?:'s|’s)?\s+wife(?:'s|’s)?\s+name\s+is\s+(?P<name>[A-Z][A-Za-z\-]{0,79})\b",
        re.UNICODE,
    )
    m = wife_pat.search(text)
    if m:
        name = _cap_span(text, m, "name")
        if name and name in text:
            ops.append(
                {
                    "op": "replace",
                    "path": "/wife_name",
                    "value": name,
                    "confidence": _CONF_EXACT,
                    "extracted_span": name,
                }
            )

    # 2) "ExamplePerson was born in Ipswich"
    born_pat = re.compile(
        r"\bKurt\s+was\s+born\s+in\s+(?P<place>[A-Z][A-Za-z\s\-\']{1,79})\b",
        re.UNICODE,
    )
    m = born_pat.search(text)
    if m:
        place = _cap_span(text, m, "place").strip()
        if place and place in text:
            ops.append(
                {
                    "op": "replace",
                    "path": "/birth_place",
                    "value": place,
                    "confidence": _CONF_EXACT,
                    "extracted_span": place,
                }
            )

    # 3) "Leo is now 6" / "Leo is 6" → kids upsert {name, age}
    # Keep it narrow: Titlecase name + integer age.
    kid_pat = re.compile(
        r"\b(?P<kid>[A-Z][a-z]{1,30})\s+is(?:\s+now)?\s+(?P<age>\d{1,3})\b",
        re.UNICODE,
    )
    m = kid_pat.search(text)
    if m:
        kid_name = _cap_span(text, m, "kid")
        age_span = _cap_span(text, m, "age")
        try:
            age_int = int(age_span)
        except Exception:
            age_int = None
        if kid_name and age_span and (age_span in text) and (kid_name in text) and isinstance(age_int, int):
            ops.append(
                {
                    "op": "add",
                    "path": "/kids",
                    "value": {"name": kid_name, "age": age_int},
                    "confidence": _CONF_EXACT,
                    "extracted_span": age_span,
                    "extracted_spans": [kid_name, age_span],
                }
            )

    # 4) "ExamplePerson worked at Meta for 5 years"
    # If we can structure role/org/duration explicitly, do career_history; otherwise, append worked_at org.
    worked_pat = re.compile(
        r"\bKurt\s+worked\s+at\s+(?P<org>[A-Z][A-Za-z0-9&\-\s]{1,80})\s+for\s+(?P<dur>\d{1,2}\s+years?)\b",
        re.UNICODE,
    )
    m = worked_pat.search(text)
    if m:
        org = _cap_span(text, m, "org").strip()
        dur = _cap_span(text, m, "dur").strip()
        if org and dur and (org in text) and (dur in text):
            ops.append(
                {
                    "op": "add",
                    "path": "/career_history",
                    "value": {"org": org, "duration": dur},
                    "confidence": _CONF_EXACT,
                    "extracted_span": org,
                    "extracted_spans": [org, dur],
                }
            )

    # 5) "Prior to that he spent 5 years as a Partner at Talented Group"
    prior_pat = re.compile(
        r"\bPrior\s+to\s+that\s+he\s+spent\s+(?P<dur>\d{1,2}\s+years?)\s+as\s+a\s+(?P<role>[A-Z][A-Za-z\-]{1,40})\s+at\s+(?P<org>[A-Z][A-Za-z0-9&\-\s]{1,80})\b",
        re.UNICODE,
    )
    m = prior_pat.search(text)
    if m:
        dur = _cap_span(text, m, "dur").strip()
        role = _cap_span(text, m, "role").strip()
        org = _cap_span(text, m, "org").strip()
        if dur and role and org and (dur in text) and (role in text) and (org in text):
            ops.append(
                {
                    "op": "add",
                    "path": "/career_history",
                    "value": {"org": org, "role": role, "duration": dur},
                    "confidence": _CONF_EXACT,
                    "extracted_span": org,
                    "extracted_spans": [dur, role, org],
                }
            )

    # Only return ops with exact confidence.
    return [op for op in ops if float(op.get("confidence", 0.0) or 0.0) >= _CONF_EXACT]

