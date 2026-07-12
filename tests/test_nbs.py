from datetime import date
from decimal import Decimal

import pytest

from ticker.nbs import NbsParseError, parse_official_eur_rate


def page(official_date="13.7.2026.", official_rate="117,3638") -> str:
    return f"""
    <table>
      <tbody>
        <tr><th class="kurs_date">индикативни на 10.7.2026.</th></tr>
        <tr><th>EUR/RSD</th></tr><tr><th class="kurs_e">999,9999</th></tr>
      </tbody>
      <tbody>
        <tr><th class="kurs_date">званични за {official_date}</th></tr>
        <tr><th class="kurs_e_2">EUR/RSD</th></tr>
        <tr><th class="kurs_e">{official_rate}</th></tr>
      </tbody>
    </table>
    """


def test_parses_only_official_rate() -> None:
    result = parse_official_eur_rate(page(), date(2026, 7, 13))
    assert result is not None
    assert result.rate == Decimal("117.3638")
    assert result.effective_date == date(2026, 7, 13)


def test_returns_none_when_only_indicative_exists() -> None:
    html = """<table><tbody><tr><th class="kurs_date">индикативни на 13.7.2026.</th></tr>
    <tr><th>EUR/RSD</th></tr><tr><th class="kurs_e">117,4</th></tr></tbody></table>"""
    assert parse_official_eur_rate(html, date(2026, 7, 13)) is None


def test_ignores_official_rate_for_different_date() -> None:
    assert parse_official_eur_rate(page(), date(2026, 7, 14)) is None


def test_rejects_duplicate_official_rates() -> None:
    html = page() + page()
    with pytest.raises(NbsParseError, match="found 2"):
        parse_official_eur_rate(html, date(2026, 7, 13))


def test_rejects_malformed_rate() -> None:
    with pytest.raises(NbsParseError, match="Invalid"):
        parse_official_eur_rate(page(official_rate="not-a-number"), date(2026, 7, 13))

