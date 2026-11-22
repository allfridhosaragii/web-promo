#!/usr/bin/env python3
"""Cek fixture wajib: CI gagal kalau ada konektor tanpa fixture (ARCH §12.1).

Aturan: setiap file connectors/<nama>.py (selain base.py) wajib punya
connectors/tests/fixtures/<source_id>/listing.html + minimal 1 detail-*.html
+ expected.json, dan test connectors/tests/test_<source_id>.py.
Jalankan: python3 services/ingest/scripts/check_fixtures.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONNECTORS = ROOT / "connectors"
FIXTURES = CONNECTORS / "tests" / "fixtures"
TESTS = CONNECTORS / "tests"

failures: list[str] = []
for path in sorted(CONNECTORS.glob("*.py")):
    if path.name in ("__init__.py", "base.py"):
        continue
    stem = path.stem  # mis. bank_bca
    source_id = re.sub(r"^(bank_|connector_)", "", stem)  # bank_bca -> bca
    fixture_dir = FIXTURES / source_id
    for required in ("listing.html", "expected.json"):
        if not (fixture_dir / required).exists():
            failures.append(f"{stem}: fixture hilang {fixture_dir / required}")
    if not list(fixture_dir.glob("detail-*.html")):
        failures.append(f"{stem}: tidak ada detail-*.html di {fixture_dir}")
    if not (TESTS / f"test_{stem}.py").exists():
        failures.append(f"{stem}: test hilang {TESTS / f'test_{stem}.py'}")

if failures:
    print("CEK FIXTURE GAGAL:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("Cek fixture lolos: setiap konektor punya fixture + test.")
