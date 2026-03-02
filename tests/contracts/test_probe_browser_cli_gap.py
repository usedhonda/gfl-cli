"""Tests for Playwright parity probe helper script."""

from __future__ import annotations

import scripts.probe_browser_cli_gap as probe


def test_normalize_probe_query_defaults_and_case_id() -> None:
    query = probe._normalize_probe_query(
        {
            'origin': 'sfo',
            'destination': 'lax',
            'date': '2026-03-23',
        },
        default_timeout=30,
        index=7,
    )

    assert query.case_id == 'case-007'
    assert query.origin == 'SFO'
    assert query.destination == 'LAX'
    assert query.lang == 'en-US'
    assert query.currency == 'USD'
    assert query.timeout_sec == 30


def test_rows_from_aria_labels_extracts_parsed_fields() -> None:
    rows = probe._rows_from_aria_labels(
        [
            (
                'Nonstop flight with Example Air. Leaves SFO at 8:30 AM and arrives at LAX at '
                '9:45 AM. Total duration 1 hr 15 min. From 123 '
            )
        ],
        top_n=5,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row['airline'] == 'Example Air'
    assert row['departure'] == '8:30 AM'
    assert row['arrival'] == '9:45 AM'
    assert row['duration'] == '1 hr 15 min'
    assert row['stops'] == 0
    assert row['price_amount'] == 123
    assert row['signature']


def test_rows_from_aria_labels_extracts_non_hyphen_stop_as_zero() -> None:
    rows = probe._rows_from_aria_labels(
        [
            (
                'Non-stop flight with Example Air. Leaves SFO at 8:30 AM and arrives at LAX at '
                '9:45 AM. Total duration 1 hr 15 min. From 123 '
            )
        ],
        top_n=5,
    )

    assert len(rows) == 1
    assert rows[0]['stops'] == 0


def test_rows_from_aria_labels_extracts_japanese_locale_fields() -> None:
    rows = probe._rows_from_aria_labels(
        [
            (
                '9820 円～。 AIR DO が運航する直行便。 火曜日, 3月 24 21:00 羽田空港発、'
                '火曜日, 3月 24 22:35 新千歳空港着。 合計時間 1 時間 35 分。'
            )
        ],
        top_n=5,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row['airline'] == 'AIR DO'
    assert row['departure'] == '21:00'
    assert row['arrival'] == '22:35'
    assert row['duration'] == '1 時間 35 分'
    assert row['stops'] == 0
    assert row['price_amount'] == 9820
    assert row['departure_min'] == 21 * 60
    assert row['arrival_min'] == 22 * 60 + 35


def test_rows_from_aria_labels_extracts_french_locale_fields() -> None:
    rows = probe._rows_from_aria_labels(
        [
            (
                'À partir de 874 euros aller-retour (prix total). '
                'Vol avec Turkish Airlines, 1 escale. Départ de Aéroport '
                'international de San Francisco à 19:40 le samedi, mars 28, arrivée '
                'à Aéroport de Paris-Charles de Gaulle à 22:30 le dimanche, mars 29. '
                'Durée totale 17 h 50 min.'
            )
        ],
        top_n=5,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row['airline'] == 'Turkish Airlines'
    assert row['departure'] == '19:40'
    assert row['arrival'] == '22:30'
    assert row['duration'] == '17 h 50 min'
    assert row['stops'] == 1
    assert row['price_amount'] == 874


def test_rows_from_aria_labels_extracts_korean_locale_fields() -> None:
    rows = probe._rows_from_aria_labels(
        [
            (
                '최저가는 381781 대한민국 원입니다. 아시아나항공의 직항 항공편입니다. '
                '일요일, 3월 29 오전 1:30에 도쿄 국제공항에서 출발하여 일요일, 3월 29 오전 4:10에 '
                '인천국제공항에 도착합니다. 총 비행 시간은 2시간 40분입니다.'
            )
        ],
        top_n=5,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row['airline'] == '아시아나항공'
    assert row['departure'] == '오전 1:30'
    assert row['arrival'] == '오전 4:10'
    assert row['duration'] == '2시간 40분'
    assert row['stops'] == 0
    assert row['price_amount'] == 381781
    assert row['departure_min'] == 90
    assert row['arrival_min'] == 250


def test_compare_rows_calculates_rates() -> None:
    cli_rows = [
        {
            'airline': 'Example Air',
            'departure': '8:00 AM',
            'arrival': '9:00 AM',
            'duration': '1 hr',
            'stops': 0,
            'price_amount': 100,
            'departure_min': 480,
            'signature': 'example|8:00 am|9:00 am|1 hr|0|100',
        },
        {
            'airline': 'Another Air',
            'departure': None,
            'arrival': '10:00 AM',
            'duration': '2 hr',
            'stops': 1,
            'price_amount': 200,
            'departure_min': None,
            'signature': 'another||10:00 am|2 hr|1|200',
        },
    ]
    browser_rows = [
        {
            'airline': 'Example Air',
            'departure': '8:00 AM',
            'arrival': '9:00 AM',
            'duration': '1 hr',
            'stops': 0,
            'price_amount': 100,
            'departure_min': 480,
            'signature': 'example|8:00 am|9:00 am|1 hr|0|100',
        }
    ]

    result = probe._compare_rows(cli_rows, browser_rows)

    assert result['required_field_fill_rate_cli'] < 1.0
    assert result['required_field_fill_rate_browser'] == 1.0
    assert result['row_signature_match_rate'] == 1.0
    assert result['time_diff_p95_min'] == 0.0
    assert result['unknown_warning_ratio'] > 0.0


def test_run_matrix_collects_success_and_failure(monkeypatch) -> None:
    queries = [
        probe.ProbeQuery(
            case_id='ok-case',
            origin='SFO',
            destination='LAX',
            date='2026-03-23',
            return_date=None,
            lang='en-US',
            currency='USD',
            timeout_sec=30,
        ),
        probe.ProbeQuery(
            case_id='ng-case',
            origin='JFK',
            destination='LHR',
            date='2026-03-23',
            return_date=None,
            lang='en-US',
            currency='USD',
            timeout_sec=30,
        ),
    ]

    def fake_probe_case(query, **_kwargs):
        if query.case_id == 'ng-case':
            raise RuntimeError('simulated failure')
        return {
            'case_id': query.case_id,
            'compare': {
                'required_field_fill_rate_cli': 1.0,
                'required_field_fill_rate_browser': 1.0,
                'row_signature_match_rate': 1.0,
                'time_diff_p95_min': 0.0,
                'unknown_warning_ratio': 0.0,
            },
        }

    monkeypatch.setattr(probe, '_probe_case', fake_probe_case)

    output = probe._run_matrix(
        queries,
        top_n=10,
        wait_ms=0,
        artifact_dir=None,
        run_id='test-run',
        screenshot=False,
        dom_snapshot=False,
        save_html=False,
    )

    assert output['mode'] == 'matrix'
    assert output['summary']['total'] == 2
    assert output['summary']['success'] == 1
    assert output['summary']['failed'] == 1
