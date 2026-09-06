from __future__ import annotations

import re
from typing import Any

import pipe_reconcile_v8 as base

# System abbreviations must be standalone CAD tokens. Without a left boundary,
# the trailing S in words such as PASS can be misread as the soil system before
# a nearby diameter (e.g. PASS Ø3/4" -> false S DN20 seed).
SYSTEM_RX = r"(?:CW|SW|RL|W|V|S)"
SYSTEM_TOKEN_RX = rf"(?<![A-Z])(?P<system>{SYSTEM_RX})(?![A-Z])"
TAG_PATTERNS = (
    re.compile(
        rf"(?P<dia>{base.DIAMETER_RX})\s*(?<![A-Z])(?P<system>{SYSTEM_RX})(?![A-Z])",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?<![A-Z])(?P<system>{SYSTEM_RX})(?![A-Z])\s*(?P<dia>{base.DIAMETER_RX})",
        re.IGNORECASE,
    ),
)


def extract_pipe_tag_classes(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").upper()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pattern in TAG_PATTERNS:
        for match in pattern.finditer(raw):
            system = match.group("system").upper()
            try:
                dia = base.normalize_diameter(match.group("dia"))
            except ValueError:
                continue
            key = (system, str(dia["diameter_key"]))
            if key in seen:
                continue
            seen.add(key)
            out.append({"system": system, **dia})
    return out
