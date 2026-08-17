"""TOON encoder for compact LLM prompt payloads.

This is intentionally used only for prompt assembly so that tool outputs remain
compact and readable before being injected into Gemini requests. API responses
returned to the frontend still use standard JSON objects.
"""

from __future__ import annotations

import json
from typing import Any


def toon_encode(data: list[dict] | dict) -> str:
    if isinstance(data, list):
        if not data:
            return "[]"
        first = data[0]
        if isinstance(first, dict) and all(isinstance(item, dict) for item in data):
            keys = list(first.keys())
            if all(set(item.keys()) == set(keys) for item in data):
                lines = [f"[{len(data)}]{{{','.join(keys)}}}:"]
                for item in data:
                    values = []
                    for key in keys:
                        value = item.get(key)
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
                        elif value is None:
                            value = ""
                        else:
                            value = str(value)
                        if "," in value:
                            value = f'"{value}"'
                        values.append(value)
                    lines.append("  " + ",".join(values))
                return "\n".join(lines)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
