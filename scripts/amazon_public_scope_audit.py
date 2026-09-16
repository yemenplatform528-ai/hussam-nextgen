#!/usr/bin/env python3
from pathlib import Path
import re, sys

DOC = Path('docs/AMAZON_HUSSAM_COMPLETENESS_AUDIT.md')
MATRIX = Path('docs/AMAZON_PUBLIC_SCOPE_MATRIX.md')
EXPECTED = 30
text = DOC.read_text(encoding='utf-8')
matrix = MATRIX.read_text(encoding='utf-8')
rows = re.findall(r'^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(CLOSED)\s*\|', text, re.M)
nums = [int(n) for n, _, _ in rows]
matrix_rows = re.findall(r'^\|\s*(\d+)\s*\|.*?\|\s*(CLOSED)\s*\|', matrix, re.M)
matrix_nums = [int(n) for n, _ in matrix_rows]
if len(rows) != EXPECTED or nums != list(range(1, EXPECTED + 1)) or len(matrix_rows) != EXPECTED or matrix_nums != list(range(1, EXPECTED + 1)):
    print(f'Amazon public scope audit: FAIL ({len(rows)}/{EXPECTED} closed rows)')
    sys.exit(1)
print(f'Amazon public scope audit: PASS ({EXPECTED}/{EXPECTED} capability families CLOSED)')
print('Scope: publicly observable Amazon capabilities; private Amazon internals are excluded by design.')
