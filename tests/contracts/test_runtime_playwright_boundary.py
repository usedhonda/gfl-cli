"""Ensure Playwright stays out of production runtime package."""

from __future__ import annotations

from pathlib import Path


def test_no_playwright_import_in_runtime_package() -> None:
    root = Path(__file__).resolve().parents[2]
    runtime_dir = root / 'gfl'

    offenders: list[str] = []
    for path in runtime_dir.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'playwright' in text.lower():
            offenders.append(str(path.relative_to(root)))

    assert not offenders, f'Playwright import/reference found in runtime package: {offenders}'
