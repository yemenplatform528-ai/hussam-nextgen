from pathlib import Path

def test_console_is_real_rtl_operational_surface():
    html = Path('app/ui/index.html').read_text()
    for needle in ['dir="rtl"','المنتجات والمخزون','المبيعات','المشتريات','المدفوعات','الشحن','المالية والمستندات','الجلسة والأمان','dashboard/summary','products','inventory/items','inventory/warehouses']:
        assert needle in html
    assert 'localStorage.setItem' in html
    assert 'replace(/[&<>"\']/' in html or 'function esc' in html

def test_version_markers_are_consistent():
    assert 'VERSION="1.0.0"' in Path('app/api/main.py').read_text()
    assert 'version = "1.0.0"' in Path('pyproject.toml').read_text()
