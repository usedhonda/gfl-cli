#!/usr/bin/env python3
"""Compare browser-rendered Google Flights structure with CLI fetch parsing shape."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fast_flights import FlightData, Passengers
from fast_flights.filter import TFSData
from fast_flights.primp import Client
from selectolax.lexbor import LexborHTMLParser

FLIGHTS_URL = 'https://www.google.com/travel/flights'
TFU_VALUE = 'EgQIABABIgA'

_AIRLINE_RE = re.compile(r'flight with (?P<airline>.+?)\. Leaves ')
_TRIP_RE = re.compile(
    r'Leaves (?P<dep_airport>.+?) at (?P<dep_time>.+?) and arrives at '
    r'(?P<arr_airport>.+?) at (?P<arr_time>.+?)\.'
)
_DURATION_RE = re.compile(r'Total duration (?P<duration>.+?)\.')
_PRICE_RE = re.compile(r'From (?P<price>[0-9][0-9,]*)(?:\D|$)')
_STOPS_RE = re.compile(r'(?P<stops>Non[- ]?stop|\d+\s*stop(?:s)?) flight with ')
_AIRLINE_JA_RE = re.compile(r'。\s*(?P<airline>.+?)\s*が運航する')
_DURATION_JA_RE = re.compile(r'合計時間\s*(?P<hour>\d+)\s*時間(?:\s*(?P<minute>\d+)\s*分)?')
_PRICE_JA_RE = re.compile(r'(?P<price>[0-9][0-9,]*)\s*円')
_STOPS_JA_RE = re.compile(r'(?P<stops>\d+)\s*回(?:の)?乗り継ぎ')
_STOPS_JA_VIA_RE = re.compile(r'経由地\s*(?P<stops>\d+)\s*か所')
_AIRLINE_FR_RE = re.compile(
    r'Vol(?:\s+direct)?\s+avec\s+(?P<airline>.+?)(?:,|\.)',
    re.IGNORECASE,
)
_DURATION_FR_RE = re.compile(
    r'Durée totale\s*(?P<hour>\d+)\s*h(?:\s*(?P<minute>\d+)\s*min)?',
    re.IGNORECASE,
)
_PRICE_FR_RE = re.compile(r'À partir de\s*(?P<price>[0-9][0-9\s,]*)\s*euros', re.IGNORECASE)
_STOPS_FR_RE = re.compile(r'(?P<stops>\d+)\s*escale', re.IGNORECASE)
_AIRLINE_KO_RE = re.compile(r'\.\s*(?P<airline>.+?)의\s*(?:직항|\d+회 경유)\s*항공편')
_DURATION_KO_RE = re.compile(r'총\s*비행\s*시간은\s*(?P<hour>\d+)시간(?:\s*(?P<minute>\d+)분)?')
_PRICE_KO_RE = re.compile(r'최저가는\s*(?P<price>[0-9][0-9,]*)\s*(?:대한민국\s*원|원)')
_STOPS_KO_RE = re.compile(r'(?P<stops>\d+)\s*회\s*경유')
_TIME_AMPM_RE = re.compile(
    r'(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AP]M)',
    re.IGNORECASE,
)
_TIME_AMPM_PREFIX_RE = re.compile(
    r'(?P<ampm>[AP]M)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})',
    re.IGNORECASE,
)
_TIME_24H_RE = re.compile(r'(?<!\d)(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)(?!\d)')
_TIME_KO_RE = re.compile(
    r'(?P<ampm>오전|오후)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})'
)


@dataclass(frozen=True)
class Metrics:
    html_length: int
    root_cards: int
    list_items: int
    price_nodes: int
    current_price_nodes: int


@dataclass(frozen=True)
class ProbeQuery:
    case_id: str
    origin: str
    destination: str
    date: str
    return_date: str | None
    lang: str
    currency: str
    timeout_sec: int


def _slug(raw: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_-]+', '-', raw.strip())
    value = value.strip('-')
    return value or 'case'


def _now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _run_id() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def _normalize_space(text: str) -> str:
    return text.replace('\u202f', ' ').replace('\xa0', ' ').strip()


def _parse_time_minutes(raw: str | None) -> int | None:
    if not raw:
        return None
    text = _normalize_space(raw)

    match = _TIME_AMPM_RE.search(text)
    if match:
        hour = int(match.group('hour'))
        minute = int(match.group('minute'))
        ampm = match.group('ampm').upper()

        if hour == 12:
            hour = 0
        if ampm == 'PM':
            hour += 12

        return hour * 60 + minute

    match = _TIME_AMPM_PREFIX_RE.search(text)
    if match:
        hour = int(match.group('hour'))
        minute = int(match.group('minute'))
        ampm = match.group('ampm').upper()

        if hour == 12:
            hour = 0
        if ampm == 'PM':
            hour += 12

        return hour * 60 + minute

    match = _TIME_24H_RE.search(text)
    if not match:
        match_ko = _TIME_KO_RE.search(text)
        if not match_ko:
            return None
        hour = int(match_ko.group('hour'))
        minute = int(match_ko.group('minute'))
        ampm_ko = match_ko.group('ampm')
        if ampm_ko == '오후' and hour != 12:
            hour += 12
        if ampm_ko == '오전' and hour == 12:
            hour = 0
        return hour * 60 + minute

    hour = int(match.group('hour'))
    minute = int(match.group('minute'))
    return hour * 60 + minute


def _parse_stops(raw: str | None) -> int | None:
    if not raw:
        return None
    text = raw.strip()
    normalized = text.lower().replace('-', '').replace(' ', '')
    if normalized == 'nonstop':
        return 0
    leading = text.split(' ', 1)[0]
    return int(leading) if leading.isdigit() else None


def _extract_departure_arrival(text: str) -> tuple[str | None, str | None]:
    trip_match = _TRIP_RE.search(text)
    if trip_match:
        return (
            _normalize_space(trip_match.group('dep_time')),
            _normalize_space(trip_match.group('arr_time')),
        )

    tokens = [match.group(0) for match in _TIME_AMPM_RE.finditer(text)]
    if len(tokens) < 2:
        tokens = [match.group(0) for match in _TIME_AMPM_PREFIX_RE.finditer(text)]
    if len(tokens) < 2:
        tokens = [match.group(0) for match in _TIME_KO_RE.finditer(text)]
    if len(tokens) < 2:
        tokens = [match.group(0) for match in _TIME_24H_RE.finditer(text)]

    if len(tokens) >= 2:
        return (_normalize_space(tokens[0]), _normalize_space(tokens[1]))

    return (None, None)


def _extract_duration(text: str) -> str | None:
    duration_match = _DURATION_RE.search(text)
    if duration_match:
        return _normalize_space(duration_match.group('duration'))

    duration_ja_match = _DURATION_JA_RE.search(text)
    if duration_ja_match:
        hour = duration_ja_match.group('hour')
        minute = duration_ja_match.group('minute')
        if minute:
            return f'{hour} 時間 {minute} 分'
        return f'{hour} 時間'

    duration_fr_match = _DURATION_FR_RE.search(text)
    if duration_fr_match:
        hour = duration_fr_match.group('hour')
        minute = duration_fr_match.group('minute')
        if minute:
            return f'{hour} h {minute} min'
        return f'{hour} h'

    duration_ko_match = _DURATION_KO_RE.search(text)
    if duration_ko_match:
        hour = duration_ko_match.group('hour')
        minute = duration_ko_match.group('minute')
        if minute:
            return f'{hour}시간 {minute}분'
        return f'{hour}시간'

    return None


def _extract_price_amount(text: str) -> int | None:
    for pattern in (_PRICE_RE, _PRICE_JA_RE, _PRICE_FR_RE, _PRICE_KO_RE):
        match = pattern.search(text)
        if not match:
            continue

        raw_price = match.group('price').replace(',', '').replace(' ', '')
        if raw_price.isdigit():
            return int(raw_price)

    return None


def _extract_airline(text: str) -> str | None:
    airline_match = _AIRLINE_RE.search(text)
    if airline_match:
        return _normalize_space(airline_match.group('airline'))

    airline_ja_match = _AIRLINE_JA_RE.search(text)
    if airline_ja_match:
        return _normalize_space(airline_ja_match.group('airline'))

    airline_fr_match = _AIRLINE_FR_RE.search(text)
    if airline_fr_match:
        return _normalize_space(airline_fr_match.group('airline'))

    airline_ko_match = _AIRLINE_KO_RE.search(text)
    if airline_ko_match:
        return _normalize_space(airline_ko_match.group('airline'))

    return None


def _extract_stops(text: str) -> int | None:
    stops_match = _STOPS_RE.search(text)
    if stops_match:
        return _parse_stops(stops_match.group('stops'))

    if '直行便' in text:
        return 0

    stops_ja_match = _STOPS_JA_RE.search(text)
    if stops_ja_match:
        return int(stops_ja_match.group('stops'))

    stops_ja_via_match = _STOPS_JA_VIA_RE.search(text)
    if stops_ja_via_match:
        return int(stops_ja_via_match.group('stops'))

    if 'Vol direct' in text or 'vol direct' in text:
        return 0

    stops_fr_match = _STOPS_FR_RE.search(text)
    if stops_fr_match:
        return int(stops_fr_match.group('stops'))

    if '직항 항공편' in text:
        return 0

    stops_ko_match = _STOPS_KO_RE.search(text)
    if stops_ko_match:
        return int(stops_ko_match.group('stops'))

    return None


def _is_candidate_flight_label(text: str) -> bool:
    if len(text) < 40:
        return False

    time_count = len(_TIME_AMPM_RE.findall(text))
    time_count += len(_TIME_24H_RE.findall(text))
    time_count += len(_TIME_KO_RE.findall(text))

    if time_count >= 2:
        return True

    hints = (
        'flight',
        'leaves',
        'arrives',
        'フライトを選択',
        '発',
        '着',
        'vol',
        'départ',
        'arrivée',
        '항공편',
        '출발',
        '도착',
    )
    lowered = text.lower()
    return any(hint in lowered or hint in text for hint in hints)


def _duration_minutes(raw: str | None) -> int | None:
    if not raw:
        return None
    text = _normalize_space(raw).lower()

    patterns = [
        re.compile(r'(?:(?P<h>\d+)\s*hr[s]?)?\s*(?:(?P<m>\d+)\s*min[s]?)?'),
        re.compile(r'(?:(?P<h>\d+)\s*h)?\s*(?:(?P<m>\d+)\s*min)?'),
        re.compile(r'(?:(?P<h>\d+)\s*時間)?\s*(?:(?P<m>\d+)\s*分)?'),
        re.compile(r'(?:(?P<h>\d+)\s*시간)?\s*(?:(?P<m>\d+)\s*분)?'),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        hour = int(match.group('h')) if match.groupdict().get('h') else 0
        minute = int(match.group('m')) if match.groupdict().get('m') else 0
        total = hour * 60 + minute
        if total > 0:
            return total

    return None


def _derive_duration_from_times(departure_min: int | None, arrival_min: int | None) -> str | None:
    if departure_min is None or arrival_min is None:
        return None

    total = (arrival_min - departure_min) % (24 * 60)
    if total <= 0:
        return None

    hour = total // 60
    minute = total % 60
    if hour > 0 and minute > 0:
        return f'{hour} hr {minute} min'
    if hour > 0:
        return f'{hour} hr'
    return f'{minute} min'


def _parse_aria_label(label: str) -> dict[str, Any]:
    text = _normalize_space(label)

    departure, arrival = _extract_departure_arrival(text)

    return {
        'airline': _extract_airline(text),
        'departure': departure,
        'arrival': arrival,
        'duration': _extract_duration(text),
        'stops': _extract_stops(text),
        'price_amount': _extract_price_amount(text),
    }


def _row_signature(row: dict[str, Any]) -> str:
    return str(row.get('departure_min') if row.get('departure_min') is not None else '')


def _rows_from_aria_labels(labels: list[str], top_n: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in labels:
        if len(rows) >= top_n:
            break

        text = _normalize_space(label)
        if not _is_candidate_flight_label(text):
            continue

        parsed = _parse_aria_label(label)
        parsed['departure_min'] = _parse_time_minutes(parsed.get('departure'))
        parsed['arrival_min'] = _parse_time_minutes(parsed.get('arrival'))
        if parsed.get('duration') is None:
            parsed['duration'] = _derive_duration_from_times(
                parsed['departure_min'],
                parsed['arrival_min'],
            )
        if parsed['departure_min'] is None or parsed['arrival_min'] is None:
            continue
        if parsed.get('airline') is None:
            continue
        if parsed.get('price_amount') is None:
            continue

        parsed['signature'] = _row_signature(parsed)
        rows.append(parsed)
    return rows


def _extract_common_snapshot(
    params: dict[str, str],
    timeout_sec: int,
    top_n: int,
) -> dict[str, Any]:
    client = Client(impersonate='chrome_144', verify=False, timeout=timeout_sec)
    response = client.get(FLIGHTS_URL, params=params, timeout=timeout_sec)

    parser = LexborHTMLParser(response.text)
    labels: list[str] = []
    for node in parser.css('ul.Rk10dc li [aria-label]'):
        label = node.attributes.get('aria-label', '')
        if label:
            labels.append(label)

    metrics = Metrics(
        html_length=len(response.text),
        root_cards=len(parser.css('div[jsname="IWWDBc"], div[jsname="YdtKid"]')),
        list_items=len(parser.css('ul.Rk10dc li')),
        price_nodes=len(parser.css('.YMlIz.FpEdX')),
        current_price_nodes=len(parser.css('span.gOatQ')),
    )

    return {
        'metrics': asdict(metrics),
        'rows': _rows_from_aria_labels(labels, top_n),
        'html': response.text,
        'labels_count': len(labels),
    }


def _extract_playwright_snapshot(
    url: str,
    timeout_sec: int,
    top_n: int,
    wait_ms: int,
    capture_html: bool,
    capture_screenshot: bool,
    capture_dom_snapshot: bool,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime environment dependent
        raise RuntimeError('playwright is required: uv run --extra design ...') from exc

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=timeout_sec * 1000)
        page.wait_for_timeout(wait_ms)

        evaluated = page.evaluate(
            """(topN) => {
                const labels = Array.from(
                    document.querySelectorAll('ul.Rk10dc li div[role="link"][aria-label]')
                )
                .slice(0, topN)
                .map((el) => el.getAttribute('aria-label') || '');

                return {
                    html_length: document.documentElement.outerHTML.length,
                    root_cards: document.querySelectorAll(
                        'div[jsname="IWWDBc"], div[jsname="YdtKid"]'
                    ).length,
                    list_items: document.querySelectorAll('ul.Rk10dc li').length,
                    price_nodes: document.querySelectorAll('.YMlIz.FpEdX').length,
                    current_price_nodes: document.querySelectorAll('span.gOatQ').length,
                    labels,
                };
            }""",
            top_n,
        )

        html = page.content() if capture_html else None
        screenshot_bytes = page.screenshot(full_page=True) if capture_screenshot else None
        dom_snapshot = None
        if capture_dom_snapshot:
            accessibility = getattr(page, 'accessibility', None)
            if accessibility is not None:
                try:
                    dom_snapshot = accessibility.snapshot()
                except Exception as exc:  # noqa: BLE001
                    dom_snapshot = {'warning': f'accessibility_snapshot_failed: {exc}'}
            else:
                dom_snapshot = {
                    'warning': 'accessibility_not_available',
                    'title': page.title(),
                }

        browser.close()

    metrics = Metrics(
        html_length=int(evaluated['html_length']),
        root_cards=int(evaluated['root_cards']),
        list_items=int(evaluated['list_items']),
        price_nodes=int(evaluated['price_nodes']),
        current_price_nodes=int(evaluated['current_price_nodes']),
    )

    labels = [str(label) for label in evaluated.get('labels', []) if str(label).strip()]
    return {
        'metrics': asdict(metrics),
        'rows': _rows_from_aria_labels(labels, top_n),
        'html': html,
        'screenshot_bytes': screenshot_bytes,
        'dom_snapshot': dom_snapshot,
        'labels_count': len(labels),
    }


def _required_fill_rate(rows: list[dict[str, Any]]) -> tuple[float, float]:
    required_fields = ('airline', 'departure', 'arrival', 'duration', 'stops', 'price_amount')
    total_fields = len(rows) * len(required_fields)
    if total_fields == 0:
        return 0.0, 0.0

    filled = 0
    for row in rows:
        for key in required_fields:
            value = row.get(key)
            if value is not None and value != '':
                filled += 1

    fill_rate = filled / total_fields
    unknown_ratio = (total_fields - filled) / total_fields
    return fill_rate, unknown_ratio


def _p95(values: list[int]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, math.ceil(0.95 * len(sorted_values)) - 1))
    return float(sorted_values[index])


def _compare_rows(
    cli_rows: list[dict[str, Any]],
    browser_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cli_fill, unknown_ratio = _required_fill_rate(cli_rows)
    browser_fill, _ = _required_fill_rate(browser_rows)

    cli_signatures = {row.get('signature') for row in cli_rows if row.get('signature')}
    browser_signatures = {row.get('signature') for row in browser_rows if row.get('signature')}

    intersection = cli_signatures & browser_signatures
    denom = max(min(len(browser_signatures), len(cli_signatures)), 1)
    row_match_rate = len(intersection) / denom

    cli_by_sig = {row.get('signature'): row for row in cli_rows if row.get('signature')}
    browser_by_sig = {row.get('signature'): row for row in browser_rows if row.get('signature')}

    time_diffs: list[int] = []
    for signature in intersection:
        cli_row = cli_by_sig.get(signature)
        browser_row = browser_by_sig.get(signature)
        if cli_row is None or browser_row is None:
            continue

        cli_depart = cli_row.get('departure_min')
        browser_depart = browser_row.get('departure_min')
        if isinstance(cli_depart, int) and isinstance(browser_depart, int):
            time_diffs.append(abs(cli_depart - browser_depart))

    return {
        'required_field_fill_rate_cli': round(cli_fill, 4),
        'required_field_fill_rate_browser': round(browser_fill, 4),
        'row_signature_match_rate': round(row_match_rate, 4),
        'time_diff_p95_min': _p95(time_diffs),
        'unknown_warning_ratio': round(unknown_ratio, 4),
        'rows_cli': len(cli_rows),
        'rows_browser': len(browser_rows),
        'matched_signatures': len(intersection),
    }


def _build_tfs(*, origin: str, destination: str, date: str, return_date: str | None) -> str:
    trip = 'round-trip' if return_date else 'one-way'
    data = [FlightData(date=date, from_airport=origin, to_airport=destination)]
    if return_date:
        data.append(FlightData(date=return_date, from_airport=destination, to_airport=origin))

    return (
        TFSData.from_interface(
            flight_data=data,
            trip=trip,
            passengers=Passengers(adults=1),
            seat='economy',
        )
        .as_b64()
        .decode('utf-8')
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(rendered + '\n', encoding='utf-8')


def _build_artifact_paths(artifact_dir: str, run_id: str, case_id: str) -> tuple[Path, Path]:
    case_root = Path(artifact_dir) / run_id / _slug(case_id)
    raw_root = case_root / 'raw'
    raw_root.mkdir(parents=True, exist_ok=True)
    return case_root, raw_root


def _probe_case(
    query: ProbeQuery,
    *,
    top_n: int,
    wait_ms: int,
    artifact_dir: str | None,
    run_id: str,
    screenshot: bool,
    dom_snapshot: bool,
    save_html: bool,
) -> dict[str, Any]:
    tfs = _build_tfs(
        origin=query.origin,
        destination=query.destination,
        date=query.date,
        return_date=query.return_date,
    )

    params: dict[str, str] = {
        'tfs': tfs,
        'hl': query.lang,
        'tfu': TFU_VALUE,
        'curr': query.currency,
    }
    url = f'{FLIGHTS_URL}?{urlencode(params)}'

    common = _extract_common_snapshot(params=params, timeout_sec=query.timeout_sec, top_n=top_n)
    browser = _extract_playwright_snapshot(
        url=url,
        timeout_sec=query.timeout_sec,
        top_n=top_n,
        wait_ms=wait_ms,
        capture_html=save_html,
        capture_screenshot=screenshot,
        capture_dom_snapshot=dom_snapshot,
    )

    common_source = 'round-trip'
    if not common['rows'] and query.return_date is not None:
        for _ in range(2):
            common_retry = _extract_common_snapshot(
                params=params,
                timeout_sec=query.timeout_sec,
                top_n=top_n,
            )
            if common_retry['rows']:
                common = common_retry
                common_source = 'round-trip-retry'
                break

    if not common['rows'] and query.return_date is not None:
        fallback_tfs = _build_tfs(
            origin=query.origin,
            destination=query.destination,
            date=query.date,
            return_date=None,
        )
        fallback_params: dict[str, str] = {
            'tfs': fallback_tfs,
            'hl': query.lang,
            'tfu': TFU_VALUE,
            'curr': query.currency,
        }
        fallback_common = _extract_common_snapshot(
            params=fallback_params,
            timeout_sec=query.timeout_sec,
            top_n=top_n,
        )
        if fallback_common['rows']:
            common = fallback_common
            common_source = 'one-way-fallback'

    compare = _compare_rows(common['rows'], browser['rows'])

    output: dict[str, Any] = {
        'generated_at_utc': _now_utc_iso(),
        'mode': 'single',
        'case_id': query.case_id,
        'query': {
            'origin': query.origin,
            'destination': query.destination,
            'date': query.date,
            'return_date': query.return_date,
            'lang': query.lang,
            'currency': query.currency,
            'url': url,
        },
        'common_fetch': {
            'source': common_source,
            'metrics': common['metrics'],
            'rows': common['rows'],
            'labels_count': common['labels_count'],
        },
        'playwright_browser': {
            'metrics': browser['metrics'],
            'rows': browser['rows'],
            'labels_count': browser['labels_count'],
        },
        'compare': compare,
    }

    if artifact_dir:
        case_root, raw_root = _build_artifact_paths(artifact_dir, run_id, query.case_id)

        _write_json(
            raw_root / 'common_fetch.json',
            {
                'query': output['query'],
                'metrics': common['metrics'],
                'rows': common['rows'],
                'labels_count': common['labels_count'],
            },
        )
        _write_json(
            raw_root / 'playwright_browser.json',
            {
                'query': output['query'],
                'metrics': browser['metrics'],
                'rows': browser['rows'],
                'labels_count': browser['labels_count'],
            },
        )

        if save_html:
            (raw_root / 'common_fetch.html').write_text(
                str(common.get('html') or ''),
                encoding='utf-8',
            )
            (raw_root / 'playwright_browser.html').write_text(
                str(browser.get('html') or ''),
                encoding='utf-8',
            )

        if screenshot and browser.get('screenshot_bytes'):
            (raw_root / 'playwright_page.png').write_bytes(browser['screenshot_bytes'])

        if dom_snapshot and browser.get('dom_snapshot'):
            _write_json(raw_root / 'playwright_dom_snapshot.json', browser['dom_snapshot'])

        _write_json(case_root / 'compare.json', output)
        output['artifact_root'] = str(case_root)

    return output


def _normalize_probe_query(raw: dict[str, Any], default_timeout: int, index: int) -> ProbeQuery:
    required = ('origin', 'destination', 'date')
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f'missing required matrix keys: {missing}')

    case_id = str(raw.get('case_id') or f'case-{index:03d}')
    return ProbeQuery(
        case_id=case_id,
        origin=str(raw['origin']).upper(),
        destination=str(raw['destination']).upper(),
        date=str(raw['date']),
        return_date=str(raw['return_date']) if raw.get('return_date') else None,
        lang=str(raw.get('lang') or 'en-US'),
        currency=str(raw.get('currency') or 'USD').upper(),
        timeout_sec=int(raw.get('timeout_sec') or default_timeout),
    )


def _load_matrix_queries(
    matrix_file: str,
    *,
    default_timeout: int,
    limit: int | None,
) -> list[ProbeQuery]:
    payload = json.loads(Path(matrix_file).read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        raise ValueError('matrix file must be a JSON array')

    normalized = [
        _normalize_probe_query(item, default_timeout=default_timeout, index=index)
        for index, item in enumerate(payload, start=1)
    ]
    if limit is not None:
        return normalized[: max(limit, 0)]
    return normalized


def _run_matrix(
    queries: list[ProbeQuery],
    *,
    top_n: int,
    wait_ms: int,
    artifact_dir: str | None,
    run_id: str,
    screenshot: bool,
    dom_snapshot: bool,
    save_html: bool,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for index, query in enumerate(queries, start=1):
        try:
            probe = _probe_case(
                query,
                top_n=top_n,
                wait_ms=wait_ms,
                artifact_dir=artifact_dir,
                run_id=run_id,
                screenshot=screenshot,
                dom_snapshot=dom_snapshot,
                save_html=save_html,
            )
            items.append({'index': index, 'status': 'success', 'probe': probe})
            success_count += 1
        except Exception as exc:  # noqa: BLE001
            items.append(
                {
                    'index': index,
                    'status': 'failed',
                    'query': asdict(query),
                    'error': str(exc),
                }
            )
            failed_count += 1

    output = {
        'generated_at_utc': _now_utc_iso(),
        'mode': 'matrix',
        'run_id': run_id,
        'artifact_dir': artifact_dir,
        'summary': {
            'total': len(queries),
            'success': success_count,
            'failed': failed_count,
        },
        'items': items,
    }

    if artifact_dir:
        run_root = Path(artifact_dir) / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        _write_json(run_root / 'matrix.json', output)

    return output


def _emit_output(output: dict[str, Any], output_path: str | None) -> None:
    rendered = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Probe browser-vs-CLI differences for Google Flights pages'
    )
    parser.add_argument('--origin')
    parser.add_argument('--destination')
    parser.add_argument('--date')
    parser.add_argument('--return-date')
    parser.add_argument('--lang', default='en-US')
    parser.add_argument('--currency', default='USD')
    parser.add_argument('--timeout-sec', type=int, default=30)
    parser.add_argument('--case-id', default='single')

    parser.add_argument('--matrix-file', help='Path to JSON array of query cases')
    parser.add_argument('--limit', type=int, help='Limit matrix cases')

    parser.add_argument('--top-n', type=int, default=20)
    parser.add_argument('--wait-ms', type=int, default=3000)
    parser.add_argument('--artifact-dir', default='artifacts/parity')
    parser.add_argument('--output', help='Write JSON output to this path')

    parser.add_argument('--screenshot', action='store_true')
    parser.add_argument('--dom-snapshot', action='store_true')
    parser.add_argument('--save-html', action='store_true')

    args = parser.parse_args()

    if args.top_n <= 0:
        parser.error('--top-n must be > 0')
    if args.wait_ms < 0:
        parser.error('--wait-ms must be >= 0')

    run_id = _run_id()
    artifact_dir = args.artifact_dir or None

    if args.matrix_file:
        queries = _load_matrix_queries(
            args.matrix_file,
            default_timeout=args.timeout_sec,
            limit=args.limit,
        )
        _emit_output(
            _run_matrix(
                queries,
                top_n=args.top_n,
                wait_ms=args.wait_ms,
                artifact_dir=artifact_dir,
                run_id=run_id,
                screenshot=args.screenshot,
                dom_snapshot=args.dom_snapshot,
                save_html=args.save_html,
            ),
            args.output,
        )
        return

    missing_single = [
        key
        for key, value in {
            'origin': args.origin,
            'destination': args.destination,
            'date': args.date,
        }.items()
        if not value
    ]
    if missing_single:
        parser.error(
            f'missing required arguments for single probe: {missing_single} '
            '(or pass --matrix-file)'
        )

    single_query = ProbeQuery(
        case_id=args.case_id,
        origin=args.origin.upper(),
        destination=args.destination.upper(),
        date=args.date,
        return_date=args.return_date,
        lang=args.lang,
        currency=args.currency.upper(),
        timeout_sec=args.timeout_sec,
    )
    _emit_output(
        _probe_case(
            single_query,
            top_n=args.top_n,
            wait_ms=args.wait_ms,
            artifact_dir=artifact_dir,
            run_id=run_id,
            screenshot=args.screenshot,
            dom_snapshot=args.dom_snapshot,
            save_html=args.save_html,
        ),
        args.output,
    )


if __name__ == '__main__':
    main()
