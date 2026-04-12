"""
测试 SEC 财务审计数据提取。
"""

from legacy.api_audit import extract_latest_fact


def test_extract_latest_fact():
    facts = {
        "facts": {
            "us-gaap": {
                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {"end": "2022-12-31", "val": 1000000000, "form": "10-K"},
                            {"end": "2023-12-31", "val": 1200000000, "form": "10-K"},
                        ]
                    }
                }
            }
        }
    }
    result = extract_latest_fact(facts, ["StockholdersEquity"])
    assert result == 1200000000


def test_extract_multiple_tags():
    facts = {
        "facts": {
            "us-gaap": {
                "RetainedEarnings": {
                    "units": {
                        "USD": [
                            {"end": "2023-12-31", "val": 500000000, "form": "10-K"},
                        ]
                    }
                }
            }
        }
    }
    result = extract_latest_fact(facts, ["RetainedEarningsAccumulatedDeficit", "RetainedEarnings"])
    assert result == 500000000


def test_extract_no_data():
    facts = {"facts": {"us-gaap": {}}}
    result = extract_latest_fact(facts, ["NonExistentTag"])
    assert result is None
