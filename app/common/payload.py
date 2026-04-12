"""
通用 payload 解析工具
处理不同格式的请求体解析（兼容 OpenAI 兼容格式和自定义格式）
"""

import json
import re
from fastapi import Request


async def parse_poffices_payload(request: Request) -> dict:
    """
    解析请求体，兼容多种格式：
    1. OpenAI 兼容格式: {"messages": [...], "content": "..."}
    2. 直接 JSON 格式
    3. 文本中包裹 JSON 格式
    """
    try:
        body = await request.json()
        if isinstance(body, dict) and "messages" in body:
            messages = body.get("messages", [])
            if messages:
                content = messages[-1].get("content", "{}")
                if isinstance(content, str):
                    try:
                        match = re.search(r'(\\{.*\\})', content, re.DOTALL)
                        if match:
                            json_str = match.group(1)
                            return json.loads(json_str)
                        return json.loads(content)
                    except Exception:
                        pass
                elif isinstance(content, dict):
                    return content
        if isinstance(body, dict) and "content" in body and isinstance(body["content"], str):
            try:
                return json.loads(body["content"])
            except Exception:
                pass
        if isinstance(body, dict):
            return body
    except Exception:
        pass
    return {}
