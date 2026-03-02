"""Tests for parity threshold gate."""

from __future__ import annotations

import json

import scripts.parity_gate as parity_gate


def test_evaluate_thresholds_pass() -> None:
    compare_items = [
        {
            'id': 'case-1',
            'compare': {
                'required_field_fill_rate_cli': 0.95,
                'required_field_fill_rate_browser': 0.99,
                'row_signature_match_rate': 0.85,
                'time_diff_p95_min': 8,
                'unknown_warning_ratio': 0.1,
            },
        }
    ]
    thresholds = {
        'required_field_fill_rate_cli': {'min': 0.9},
        'required_field_fill_rate_browser': {'min': 0.95},
        'row_signature_match_rate': {'min': 0.7},
        'time_diff_p95_min': {'max': 15},
        'unknown_warning_ratio': {'max': 0.25},
    }

    evaluation = parity_gate.evaluate_thresholds(compare_items, thresholds)
    assert evaluation['status'] == 'pass'
    assert evaluation['failed_cases'] == 0


def test_evaluate_thresholds_fail_on_min_violation() -> None:
    compare_items = [
        {
            'id': 'case-1',
            'compare': {
                'required_field_fill_rate_cli': 0.6,
                'required_field_fill_rate_browser': 0.99,
                'row_signature_match_rate': 0.85,
                'time_diff_p95_min': 8,
                'unknown_warning_ratio': 0.1,
            },
        }
    ]
    thresholds = {'required_field_fill_rate_cli': {'min': 0.9}}

    evaluation = parity_gate.evaluate_thresholds(compare_items, thresholds)
    assert evaluation['status'] == 'fail'
    assert evaluation['failed_cases'] == 1
    assert evaluation['violations'][0]['reason'] == 'below_min'


def test_run_gate_fails_when_no_successful_cases(tmp_path) -> None:
    input_path = tmp_path / 'matrix.json'
    thresholds_path = tmp_path / 'thresholds.json'

    input_path.write_text(
        json.dumps(
            {
                'mode': 'matrix',
                'items': [
                    {
                        'index': 1,
                        'status': 'failed',
                        'error': 'timeout',
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    thresholds_path.write_text(
        json.dumps({'row_signature_match_rate': {'min': 0.7}}),
        encoding='utf-8',
    )

    exit_code, evaluation = parity_gate.run_gate(str(input_path), str(thresholds_path))

    assert exit_code == 1
    assert evaluation['status'] == 'fail'
    assert evaluation['total_cases'] == 0
