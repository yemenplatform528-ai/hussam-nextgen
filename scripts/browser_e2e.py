#!/usr/bin/env python3
"""Engineering browser UI contract run for Hussam NextGen."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "app/ui"

MOCK = r"""
window.__e2eStorage={_:{},getItem(k){return this._[k]??null},setItem(k,v){this._[k]=String(v)},removeItem(k){delete this._[k]}};
(() => {
  const originalFetch = window.fetch.bind(window);
  const listing = {id: 1, title: 'E2E Phone', description: 'Browser journey product', unit_price: '1500', currency: 'YER', stock: null, seller: {slug: 'e2e-store', display_name: 'E2E Store', description: 'Browser test store'}};
  const json = (data, status=200) => Promise.resolve(new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}}));
  window.fetch = (input, options={}) => {
    const url = String(input);
    if (url.endsWith('/platform/market-context/YEM')) return json({schema_version:'1.0',market:{code:'YEM',country_code:'YE',name:'Yemen',locale:'ar-YE',timezone:'Asia/Aden',default_currency:'YER',status:'active'},money:{currencies:[{currency:'YER',is_default:true,cash_supported:true,electronic_supported:true}],money_units:[{code:'YER_CURRENT',currency:'YER',variant:'current',name:'Yemeni rial',name_ar:'ريال يمني'}]},payments:{methods:[{code:'cod',name:'Cash on delivery',method_type:'cod',requires_provider:false}]},geography:{coverage:[]},delivery:{modes:['pickup','local_delivery']},connectivity:{offline_drafts:true,idempotent_mutations:true,explicit_pending_states:true},documents:{lifecycle:['draft','finalized','void'],versioned:true,immutable_versions:true,arabic_first:true,templates:[]},notifications:{channels:['in_app'],tenant_scoped:true},ai_hus:{market_context:{market_code:'YEM',country_code:'YE',locale:'ar-YE',timezone:'Asia/Aden',default_currency:'YER'},governance:{ai_proposes_not_authorizes:true,hus_uses_domain_contracts:true},arabic_terminology:true,local_market_context:true},capabilities:[]});\n    if (url.includes('/marketplace/listings?')) return json({items:[listing], total:1, limit:24, offset:0, sort:'relevance'});
    if (url.endsWith('/marketplace/categories')) return json({items:[{id:1, slug:'e2e-category', name:'E2E Category', parent_id:null}]});
    if (url.includes('/marketplace/sellers?')) return json({items:[{tenant_id:1, slug:'e2e-store', display_name:'E2E Store', description:'Browser test store', seller_type:'business'}]});
    if (url.endsWith('/session')) return json({user_id:'e2e-user', tenant_id:1, membership_id:1});
    if (url.endsWith('/marketplace/seller/center')) return json({metrics:{listings_published:1,listings_total:1,orders_actionable:0,fulfillments_actionable:0,net:0,currency:'YER'},actions:[],recent_orders:[]});
    if (url.endsWith('/marketplace/seller/catalog')) return json({items:[]});
    if (url.endsWith('/marketplace/buyer/cart')) return json({items:[]});
    return originalFetch(input, options);
  };
})();
"""


def build_page(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    html = (ROOT / "index.html").read_text()
    css = (ROOT / "styles.css").read_text()
    js = (ROOT / "app.js").read_text().replace("localStorage.", "window.__e2eStorage.")
    html = html.replace('<link rel="stylesheet" href="styles.css">', f'<style>{css}</style>')
    html = html.replace('<script src="app.js"></script>', '')
    page.set_content(html)
    page.add_script_tag(content=MOCK)
    page.add_script_tag(content=js)
    page.wait_for_timeout(250)
    return page


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        try:
            for width, height in ((1440, 1000), (390, 844)):
                page = build_page(browser, width, height)
                try:
                    assert page.title() == "Hussam — شبكة التجارة"
                    assert page.locator("h1", has_text="كل ما تحتاجه، في Hussam.").is_visible()
                    assert page.locator("text=E2E Phone").is_visible()
                    page.locator("button[data-action='account']").click()
                    assert page.locator("a[href='/api/v1/auth/oidc/login']").is_visible()
                    assert page.locator("text=HttpOnly cookie").is_visible()
                    page.locator("textarea[name='token']").fill("engineering-test-token")
                    page.locator("#tokenForm button").click()
                    page.wait_for_timeout(150)
                    page.locator("button[data-action='account']").click()
                    page.locator("button[data-action='seller']").click()
                    assert page.locator("#workspaceView").is_visible()
                    assert page.locator(".workspace-nav").is_visible()
                    page.locator("button[data-ws='products']").click()
                    page.wait_for_timeout(250)
                    assert page.locator(".workspace-nav button[data-ws='products']").is_visible()
                finally:
                    page.close()
        finally:
            browser.close()
    print("BROWSER_E2E_OK desktop+mobile")


if __name__ == "__main__":
    run()
