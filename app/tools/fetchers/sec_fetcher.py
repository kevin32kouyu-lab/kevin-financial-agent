"""SEC EDGAR data fetcher.

Provides primary source for audit and filing data.
"""

from datetime import date
from typing import Any

from app.core.config import AppSettings

from .base import _get_cik_mapping

import requests

SEC_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 research-contact@example.com",
}


def _extract_latest_fact(facts: dict[str, Any], tags: list[str]) -> float | int | None:
    """Extract latest fact from SEC XBRL data.

    Args:
        facts: SEC facts dictionary
        tags: List of fact tags to search for

    Returns:
        Latest fact value or None if not found
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        if tag not in us_gaap:
            continue
        try:
            data_points = us_gaap[tag].get("units", {}).get("USD", [])
            valid_points = [point for point in data_points if point.get("form") in {"10-K", "10-Q"}]
            valid_points.sort(key=lambda point: point.get("end", ""))
            if valid_points:
                return valid_points[-1].get("val")
        except Exception:
            continue
    return None


def _fetch_recent_filings(cik: int) -> list[dict[str, Any]]:
    """Fetch recent SEC filings for a company.

    Args:
        cik: SEC Central Index Key (10-digit)

    Returns:
        List of recent filings with form type, dates, and URLs
    """
    response = requests.get(
        f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json",
        headers=SEC_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    filing_dates = recent.get("filingDate", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    primary_documents = recent.get("primaryDocument", []) or []

    filings: list[dict[str, Any]] = []
    for index, form_type in enumerate(forms[:8]):
        accession_number = accession_numbers[index] if index < len(accession_numbers) else ""
        primary_document = primary_documents[index] if index < len(primary_documents) else ""
        filed_at = filing_dates[index] if index < len(filing_dates) else ""
        archive_accession = accession_number.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{archive_accession}/{primary_document}"
            if archive_accession and primary_document
            else ""
        )
        filings.append(
            {
                "form": form_type,
                "filed_at": filed_at,
                "accession_number": accession_number,
                "primary_document": primary_document,
                "filing_url": filing_url,
            }
        )
    return filings


def fetch_sec_audit_data(ticker: str) -> dict[str, Any]:
    """Fetch audit and solvency data from SEC EDGAR.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with debt ratios, liquidity metrics, and risk flags
    """
    try:
        cik = _get_cik_mapping().get(str(ticker).upper())
        if not cik:
            return {"Ticker": ticker, "Status": "Not Found in SEC", "Source": "sec_edgar"}

        recent_filings = _fetch_recent_filings(cik)
        filing_summary = ", ".join(
            f"{item['form']} ({item['filed_at']})" for item in recent_filings[:3] if item.get("form")
        )

        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json"
        response = requests.get(facts_url, headers=SEC_HEADERS, timeout=12)
        if response.status_code != 200:
            return {
                "Ticker": ticker,
                "Status": f"SEC API Rejected: {response.status_code}",
                "Recent_Filings": recent_filings,
                "Recent_Filing_Summary": filing_summary or "No recent filings found.",
                "Source": "sec_edgar",
            }

        facts = response.json()
        equity = _extract_latest_fact(facts, ["StockholdersEquity", "LiabilitiesAndStockholdersEquity"])
        debt = _extract_latest_fact(facts, ["LongTermDebt", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligations"]) or 0
        current_assets = _extract_latest_fact(facts, ["AssetsCurrent"])
        current_liabilities = _extract_latest_fact(facts, ["LiabilitiesCurrent"])
        retained_earnings = _extract_latest_fact(facts, ["RetainedEarningsAccumulatedDeficit", "RetainedEarnings"])

        base_payload = {
            "Ticker": ticker,
            "Recent_Filings": recent_filings,
            "Recent_Filing_Summary": filing_summary or "No recent filings found.",
            "Latest_Filing_Date": recent_filings[0]["filed_at"] if recent_filings else None,
            "Recent_Filing_Forms": [item["form"] for item in recent_filings[:3]],
            "Source": "sec_edgar",
        }

        if not current_assets or not current_liabilities or not equity:
            return {
                **base_payload,
                "Status": "Data Tag Mismatch",
            }

        de_ratio = round(debt / equity, 2) if equity > 0 else "N/A"
        current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else "N/A"
        retained_b = round(retained_earnings / 1_000_000_000, 2) if retained_earnings else "N/A"

        risk_flags: list[str] = []
        if isinstance(de_ratio, float) and de_ratio > 2.0:
            risk_flags.append(f"High leverage (D/E: {de_ratio})")
        if isinstance(current_ratio, float) and current_ratio < 1.0:
            risk_flags.append(f"Liquidity pressure (Current Ratio: {current_ratio})")
        if isinstance(retained_b, float) and retained_b < -1.0:
            risk_flags.append(f"Large accumulated deficit ({retained_b}B USD)")

        overall_risk = "High Risk" if len(risk_flags) >= 2 else ("Medium Risk" if risk_flags else "Safe")
        return {
            **base_payload,
            "Debt_to_Equity": de_ratio,
            "Current_Ratio": current_ratio,
            "Retained_Earnings_B": retained_b,
            "Risk_Flags": risk_flags or ["No material audit flags"],
            "Overall_Risk_Level": overall_risk,
            "Status": "Success",
        }
    except Exception as exc:
        return {"Ticker": ticker, "Status": f"Failed: {exc}", "Source": "sec_edgar"}


def fetch_historical_audit_data(ticker: str, as_of_date: date) -> dict[str, Any]:
    """Get historical audit data placeholder.

    Note: Current free-data stack does not provide reliable historical SEC replay.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Historical date

    Returns:
        Dictionary indicating historical data unavailable
    """
    return {
        "Ticker": ticker,
        "Status": "Historical SEC filing view unavailable",
        "Overall_Risk_Level": "Historical data unavailable",
        "Risk_Flags": ["Historical SEC replay is not available in the current free-data stack."],
        "Latest_Filing_Date": None,
        "Recent_Filing_Summary": f"Unavailable as of {as_of_date.isoformat()}",
        "Source": "historical_unavailable",
        "As_Of_Date": as_of_date.isoformat(),
    }


def fetch_historical_smart_money_data(ticker: str, as_of_date: date) -> dict[str, Any]:
    """Get historical smart money data placeholder.

    Note: Current free-data stack does not provide reliable historical positioning replay.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Historical date

    Returns:
        Dictionary indicating historical data unavailable
    """
    return {
        "Ticker": ticker,
        "Status": "Historical smart money proxy unavailable",
        "Smart_Money_Signal": "Unavailable as-of history. The current free-data stack does not provide reliable historical positioning replay.",
        "Source": "historical_unavailable",
        "As_Of_Date": as_of_date.isoformat(),
    }
