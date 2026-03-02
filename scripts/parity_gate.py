#!/usr/bin/env python3
"""Parity threshold gate for browser-vs-fetch probe results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_thresholds(path: str) -> dict[str, dict[str, float]]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('thresholds file must be a JSON object')

    normalized: dict[str, dict[str, float]] = {}
    for metric, rule in payload.items():
        if not isinstance(rule, dict):
            raise ValueError(f'threshold rule must be object: {metric}')

        item: dict[str, float] = {}
        if 'min' in rule:
            item['min'] = float(rule['min'])
        if 'max' in rule:
            item['max'] = float(rule['max'])
        if not item:
            raise ValueError(f'threshold rule must include min and/or max: {metric}')

        normalized[metric] = item

    return normalized


def extract_compare_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mode = payload.get('mode')

    if mode == 'matrix':
        result: list[dict[str, Any]] = []
        for index, item in enumerate(payload.get('items', []), start=1):
            if item.get('status') != 'success':
                continue
            probe = item.get('probe')
            if not isinstance(probe, dict):
                continue

            compare = probe.get('compare')
            if not isinstance(compare, dict):
                continue

            result.append(
                {
                    'id': str(probe.get('case_id') or f'case-{index:03d}'),
                    'compare': compare,
                }
            )
        return result

    if mode == 'single' or 'compare' in payload:
        compare = payload.get('compare')
        if not isinstance(compare, dict):
            return []
        return [{'id': str(payload.get('case_id') or 'single'), 'compare': compare}]

    return []


def evaluate_thresholds(
    compare_items: list[dict[str, Any]],
    thresholds: dict[str, dict[str, float]],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    passed_cases = 0

    for item in compare_items:
        case_id = str(item['id'])
        compare = item['compare']
        case_failed = False

        for metric, rule in thresholds.items():
            value = compare.get(metric)
            if not isinstance(value, (int, float)):
                violations.append(
                    {
                        'case_id': case_id,
                        'metric': metric,
                        'reason': 'missing_or_non_numeric',
                        'value': value,
                    }
                )
                case_failed = True
                continue

            metric_value = float(value)
            min_value = rule.get('min')
            max_value = rule.get('max')

            if min_value is not None and metric_value < min_value:
                violations.append(
                    {
                        'case_id': case_id,
                        'metric': metric,
                        'reason': 'below_min',
                        'value': metric_value,
                        'min': min_value,
                    }
                )
                case_failed = True

            if max_value is not None and metric_value > max_value:
                violations.append(
                    {
                        'case_id': case_id,
                        'metric': metric,
                        'reason': 'above_max',
                        'value': metric_value,
                        'max': max_value,
                    }
                )
                case_failed = True

        if not case_failed:
            passed_cases += 1

    total_cases = len(compare_items)
    failed_cases = total_cases - passed_cases

    return {
        'status': 'pass' if failed_cases == 0 and total_cases > 0 else 'fail',
        'total_cases': total_cases,
        'passed_cases': passed_cases,
        'failed_cases': failed_cases,
        'violations': violations,
    }


def run_gate(input_path: str, thresholds_path: str) -> tuple[int, dict[str, Any]]:
    payload = json.loads(Path(input_path).read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('input payload must be a JSON object')

    thresholds = load_thresholds(thresholds_path)
    compare_items = extract_compare_items(payload)
    evaluation = evaluate_thresholds(compare_items, thresholds)

    if evaluation['total_cases'] == 0:
        evaluation['status'] = 'fail'
        evaluation['violations'].append(
            {
                'case_id': 'global',
                'metric': 'compare_items',
                'reason': 'no_successful_cases_found',
                'value': 0,
            }
        )

    exit_code = 0 if evaluation['status'] == 'pass' else 1
    return exit_code, evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description='Parity threshold gate')
    parser.add_argument('--input', required=True, help='Probe output JSON (single or matrix)')
    parser.add_argument(
        '--thresholds',
        default='docs/parity/thresholds.json',
        help='Threshold rules JSON path',
    )
    parser.add_argument('--output', help='Optional path to write evaluation JSON')
    args = parser.parse_args()

    exit_code, evaluation = run_gate(args.input, args.thresholds)
    rendered = json.dumps(evaluation, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
