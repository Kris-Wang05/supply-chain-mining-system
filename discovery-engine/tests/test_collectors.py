from __future__ import annotations

from datetime import date

from discovery_engine.collectors.edgar_8k import (
    accession_from_path,
    daily_index_url,
    map_items_to_event_type,
    parse_daily_index,
    parse_items_from_index_html,
)
from discovery_engine.collectors.edgar_form4 import is_routine, parse_form4_xml

SAMPLE_IDX = """Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    July 7, 2026

Form Type   Company Name                       CIK         Date Filed  File Name
---------------------------------------------------------------------------------
4           DOE JOHN                           0001234567  20260707    edgar/data/1234567/0001234567-26-000001.txt
8-K         EXAMPLE CORP                       0000320193  20260707    edgar/data/320193/0000320193-26-000042.txt
8-K/A       AMENDED INC                        0000999999  20260707    edgar/data/999999/0000999999-26-000007.txt
10-Q        OTHER CO                           0000111111  20260707    edgar/data/111111/0000111111-26-000003.txt
"""

SAMPLE_INDEX_HTML = """<html><body>
<div class="formGrouping"><div class="infoHead">Items</div>
<div class="info">1.01, 9.01</div></div>
Items 1.01, 9.01
</body></html>"""

SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerCik>0000320193</issuerCik><issuerName>Example Corp</issuerName>
    <issuerTradingSymbol>XYZ</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>DOE JOHN</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>0</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>13.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_daily_index_filters_by_form_prefix() -> None:
    entries = parse_daily_index(SAMPLE_IDX, form_prefix="8-K")
    assert len(entries) == 2  # 8-K 和 8-K/A
    assert entries[0]["company"] == "EXAMPLE CORP"
    assert entries[0]["cik"] == "320193"
    assert entries[0]["filed_date"] == "2026-07-07"
    assert entries[0]["path"].endswith("0000320193-26-000042.txt")


def test_parse_daily_index_form4_exact() -> None:
    entries = parse_daily_index(SAMPLE_IDX, form_prefix="4")
    assert len(entries) == 1
    assert entries[0]["form"] == "4"


def test_accession_from_path() -> None:
    assert (
        accession_from_path("edgar/data/320193/0000320193-26-000042.txt")
        == "0000320193-26-000042"
    )


def test_daily_index_url() -> None:
    assert daily_index_url(date(2026, 7, 7)) == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/form.20260707.idx"
    )


def test_parse_items_from_index_html() -> None:
    assert parse_items_from_index_html(SAMPLE_INDEX_HTML) == ["1.01", "9.01"]
    assert parse_items_from_index_html("<html>no items</html>") == []


def test_map_items_to_event_type() -> None:
    assert map_items_to_event_type(["1.01", "9.01"]) == ("formal_agreement", False)
    assert map_items_to_event_type(["2.02"]) == ("financial_inflection", False)
    assert map_items_to_event_type(["8.01"]) == ("", True)
    assert map_items_to_event_type([]) == ("", True)


def test_parse_form4_xml_sums_only_p_transactions() -> None:
    parsed = parse_form4_xml(SAMPLE_FORM4_XML)
    assert parsed["insider_name"] == "DOE JOHN"
    assert parsed["issuer_ticker"] == "XYZ"
    assert parsed["purchase_total_usd"] == 125000.0
    assert parsed["purchase_shares"] == 10000.0
    assert not parsed["is_10b5_1"]


def test_is_routine_thresholds() -> None:
    assert is_routine({"purchase_total_usd": 10000, "is_10b5_1": False})
    assert is_routine({"purchase_total_usd": 999999, "is_10b5_1": True})
    assert not is_routine({"purchase_total_usd": 125000, "is_10b5_1": False})
