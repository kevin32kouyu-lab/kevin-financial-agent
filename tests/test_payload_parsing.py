"""
测试通用 payload 解析。
"""

from app.common.payload import parse_poffices_payload


class MockRequest:
    def __init__(self, json_body):
        self._json = json_body

    async def json(self):
        return self._json


async def test_direct_dict():
    req = MockRequest({"comparison_matrix": [{"Ticker": "AAPL"}]})
    result = await parse_poffices_payload(req)
    assert "comparison_matrix" in result
    assert result["comparison_matrix"][0]["Ticker"] == "AAPL"


async def test_openai_format():
    req = MockRequest(
        {
            "messages": [
                {"role": "user", "content": "{\"comparison_matrix\": [{\"Ticker\": \"MSFT\"}]}"}
            ]
        }
    )
    result = await parse_poffices_payload(req)
    assert "comparison_matrix" in result


async def test_direct_content_json():
    req = MockRequest({"content": "{\"comparison_matrix\": [{\"Ticker\": \"GOOG\"}]}"})
    result = await parse_poffices_payload(req)
    assert "comparison_matrix" in result
    assert result["comparison_matrix"][0]["Ticker"] == "GOOG"


async def test_empty_request():
    req = MockRequest(None)
    result = await parse_poffices_payload(req)
    assert result == {}
