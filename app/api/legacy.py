from __future__ import annotations

import json
import re
from typing import Any

from fastapi import Request

from app.domain.contracts import DebugAnalysisRequest


async def parse_legacy_payload(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}

    if not isinstance(body, dict):
        return {}

    if "messages" in body:
        messages = body.get("messages") or []
        if messages:
            content = messages[-1].get("content", "{}")
            if isinstance(content, dict):
                return content
            if isinstance(content, str):
                try:
                    match = re.search(r"(\{.*\})", content, re.DOTALL)
                    return json.loads(match.group(1) if match else content)
                except Exception:
                    pass

    if isinstance(body.get("content"), str):
        try:
            return json.loads(body["content"])
        except Exception:
            pass

    return body


def extract_tickers_from_matrix(payload: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in payload.get("comparison_matrix", []):
        ticker = str(item.get("Ticker", "")).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return output


def build_debug_request(payload: dict[str, Any]) -> DebugAnalysisRequest:
    return DebugAnalysisRequest.model_validate(payload)
