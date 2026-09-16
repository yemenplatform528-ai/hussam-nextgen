from pathlib import Path

root = Path(__file__).resolve().parents[1]
html = (root / 'app/ui/index.html').read_text(encoding='utf-8')
js = (root / 'app/ui/app.js').read_text(encoding='utf-8')
css = (root / 'app/ui/styles.css').read_text(encoding='utf-8')
required_html = ['customerView','workspaceView','customerHome','customerSearch','customerCart','customerCheckout','customerOrders','customerAccount']
required_api = ['/marketplace/listings','/marketplace/buyer/cart','/marketplace/buyer/checkout','/marketplace/buyer/orders','/marketplace/seller/orders','/marketplace/seller/payouts']
for marker in required_html:
    assert marker in html, f'missing UI marker: {marker}'
for route in required_api:
    assert route in js, f'missing API integration: {route}'
assert 'dir="rtl"' in html
assert '--accent' in css
print('UI audit: PASS')
