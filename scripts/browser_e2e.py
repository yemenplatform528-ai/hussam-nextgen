#!/usr/bin/env python3
"""Engineering browser UI contract run for Hussam NextGen."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "app/ui"

MOCK = r"""
window.__e2eStorage={_:{},getItem(k){return this._[k]??null},setItem(k,v){this._[k]=String(v)},removeItem(k){delete this._[k]}};
window.__e2eCheckoutCalls=0;
window.__e2eLoseFirstCheckoutResponse=true;
window.__e2eLastCheckoutHeaders=null;
window.__e2eLastCheckoutBody=null;
window.__e2eSellerRegistered=true;
window.__e2eSellerVerification='approved';
window.__e2eCartMutationCalls=0;
window.__e2eLastCartMutationHeaders=null;
window.__e2eOfflineReads=false;
window.__e2eCheckoutContextUrl='';
window.__e2eAddresses=[];
window.__e2eInventoryItems=[];
window.__e2eInventoryRequests=[];
window.__e2eWarehouses=[];
window.__e2eInventoryMovements=[];
window.__e2eCatalogItems=[];
window.__e2eSellerOrders=[];
window.__e2ePackages=[];
window.__e2eCODCollections=[];
window.__e2eBuyerReturns=[];
window.__e2eDisputes=[];
window.__e2eReturns=[];
(() => {
  const originalFetch = window.fetch.bind(window);
  const listing = {id: 1, title: 'E2E Phone', description: 'Browser journey product', unit_price: '1500', currency: 'YER', stock: null, seller: {tenant_id: 1, slug: 'e2e-store', display_name: 'E2E Store', description: 'Browser test store'}};
  const json = (data, status=200) => Promise.resolve(new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}}));
  window.fetch = (input, options={}) => {
    const url = String(input);
    window.__e2eInventoryRequests.push({url, method: options.method || 'GET'});
    if (window.__e2eOfflineReads && (url.includes('/marketplace/listings?') || url.endsWith('/marketplace/categories') || url.includes('/marketplace/sellers?'))) return Promise.reject(new TypeError('offline'));
    if (url.includes('/marketplace/listings?')) return json({items:[listing], total:1, limit:24, offset:0, sort:'relevance'});
    if (url.endsWith('/marketplace/categories')) return json({items:[{id:1, slug:'e2e-category', name:'E2E Category', parent_id:null}]});
    if (url.includes('/marketplace/sellers?')) return json({items:[{tenant_id:1, slug:'e2e-store', display_name:'E2E Store', description:'Browser test store', seller_type:'business'}]});
    if (url.endsWith('/session')) return json({user_id:'e2e-user', tenant_id:1, membership_id:1});
    if (url.endsWith('/marketplace/seller') && options.method==='POST') { window.__e2eSellerRegistered=true; window.__e2eSellerVerification='pending'; return json({tenant_id:1,slug:'taiz-market',display_name:'متجر تعز',status:'pending'},201); }
    if (url.endsWith('/marketplace/seller/verification') && options.method==='POST') { window.__e2eSellerVerification='pending'; return json({id:1,status:'pending'}); }
    if (url.endsWith('/marketplace/seller/center')) return json(window.__e2eSellerRegistered?{registered:true,seller:{tenant_id:1,slug:'taiz-market',display_name:'متجر تعز',status:window.__e2eSellerVerification==='approved'?'active':'pending',verification:window.__e2eSellerVerification},metrics:{listings_published:1,listings_total:1,orders_actionable:0,fulfillments_actionable:0,net:0,currency:'YER'},actions:[],recent_orders:[]}:{registered:false,actions:[],metrics:{}});
    if (url.endsWith('/marketplace/seller/orders')) return json({items:window.__e2eSellerOrders});
    if (url.endsWith('/marketplace/seller/returns')) return json({items:window.__e2eReturns});
    if (url.match(/\/marketplace\/seller\/returns\/\d+\/review$/) && options.method==='POST') { const id=Number(url.match(/returns\/(\d+)\/review$/)[1]); const body=JSON.parse(options.body||'{}'); const x=window.__e2eReturns.find(r=>r.id===id); x.status=body.decision; return json({id,status:x.status}); }
    if (url.match(/\/marketplace\/seller\/returns\/\d+\/transition$/) && options.method==='POST') { const id=Number(url.match(/returns\/(\d+)\/transition$/)[1]); const body=JSON.parse(options.body||'{}'); const x=window.__e2eReturns.find(r=>r.id===id); x.status=body.status; return json({id,status:x.status}); }
    if (url.match(/\/marketplace\/seller\/returns\/\d+\/approve-refund$/) && options.method==='POST') { const id=Number(url.match(/returns\/(\d+)\/approve-refund$/)[1]); const x=window.__e2eReturns.find(r=>r.id===id); x.status='refund_approved'; x.refund_amount='2500'; x.refund_currency='YER'; x.refund_reference='REFUND-E2E-001'; return json({return_id:id,status:x.status,refund:{reference:x.refund_reference,amount:x.refund_amount,currency:x.refund_currency,status:'pending'}}); }
    if (url.match(/\/marketplace\/seller\/returns\/\d+\/complete-refund$/) && options.method==='POST') { const id=Number(url.match(/returns\/(\d+)\/complete-refund$/)[1]); const body=JSON.parse(options.body||'{}'); const x=window.__e2eReturns.find(r=>r.id===id); x.status='refunded'; return json({return_id:id,status:x.status,provider_refund_id:body.provider_refund_id}); }
    if (url.endsWith('/marketplace/seller/orders/99/processing') && options.method==='POST') { window.__e2eSellerOrders[0].status='processing'; return json({id:99,status:'processing'}); }
    if (url.endsWith('/marketplace/seller/orders/199/fulfillments') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); Object.assign(window.__e2eSellerOrders[0],{fulfillment_id:701,fulfillment_status:'pending',fulfillment_method:body.method,shipment_id:null,carrier:null}); return json({id:701,seller_order_id:199,method:body.method,status:'pending'},201); }
    if (url.endsWith('/marketplace/seller/fulfillments/701/transition') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); window.__e2eSellerOrders[0].fulfillment_status=body.status; if(body.status==='delivered') window.__e2eSellerOrders[0].status='completed'; return json({id:701,status:body.status,shipment_id:window.__e2eSellerOrders[0].shipment_id}); }
    if (url.endsWith('/marketplace/seller/fulfillments/701/packages') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); window.__e2ePackages.push(body); return json({id:801,fulfillment_id:701,reference:body.reference,status:'packed'},201); }
    if (url.endsWith('/marketplace/seller/fulfillments/701/shipment') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); Object.assign(window.__e2eSellerOrders[0],{shipment_id:901,carrier:body.carrier,fulfillment_status:'ready'}); return json({fulfillment_id:701,shipment:{id:901,reference:'SHP-E2E',status:'ready',carrier:body.carrier,tracking_number:body.tracking_number}},201); }
    if (url.endsWith('/marketplace/seller/fulfillments/701/cod-collection') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); window.__e2eCODCollections.push(body); window.__e2eSellerOrders[0].cod_collection_id=1001; window.__e2eSellerOrders[0].cod_collection_status='collected'; return json({id:1001,shipment_id:901,reference:body.reference,amount:body.amount,currency:body.currency,status:'collected'},201); }
    if (url.endsWith('/inventory/items') && options.method==='POST') { const item=JSON.parse(options.body||'{}'); window.__e2eInventoryItems.push({...item,active:true}); return json(item,201); }
    if (url.includes('/warehouses') && String(options.method || 'GET').toUpperCase()==='POST') { const warehouse=JSON.parse(options.body||'{}'); window.__e2eWarehouses.push({...warehouse,active:true}); return json(warehouse,201); }
    if (url.endsWith('/inventory/movements') && options.method==='POST') { const movement=JSON.parse(options.body||'{}'); window.__e2eInventoryMovements.push({...movement,id:window.__e2eInventoryMovements.length+1}); return json({id:1,reference:movement.reference,direction:movement.direction,quantity:movement.quantity},201); }
    if (url.endsWith('/inventory/movements')) return json({items:window.__e2eInventoryMovements});
    if (url.includes('/inventory/stock/')) return json({item_id:'rice-10kg',warehouse_id:'main-warehouse',on_hand:'50',reserved:'0',available:'50'});
    if (url.endsWith('/products')) return json({items:window.__e2eInventoryItems,limit:50,offset:0});
    if ((url.endsWith('/warehouses') || url.includes('/warehouses?')) && String(options.method || 'GET').toUpperCase()!=='POST') return json({items:window.__e2eWarehouses,limit:50,offset:0});
    if (url.endsWith('/marketplace/seller/catalog/bundle') && options.method==='POST') { const body=JSON.parse(options.body||'{}'); window.__e2eCatalogItems.push({name:body.product.name,slug:body.product.slug,skus:[{sku_code:body.sku.sku_code,offer:{unit_price:body.offer.unit_price,currency:body.offer.currency,status:'active'},listing:{slug:body.listing_slug,status:'draft'}}]}); return json({product:{id:1,slug:body.product.slug,name:body.product.name},sku:{id:1,sku_code:body.sku.sku_code},offer:{id:1,currency:body.offer.currency,unit_price:body.offer.unit_price},listing:{id:1,slug:body.listing_slug,status:'draft',moderation_status:'pending'}},201); }
    if (url.endsWith('/marketplace/seller/catalog')) return json({items:window.__e2eCatalogItems});
    if (url.endsWith('/marketplace/buyer/cart')) return json({id:1,status:'active',market_id:1,market_code:'YEM',items:[{id:1,quantity:'1',line_total:'1500',listing}]});
    if (url.endsWith('/marketplace/buyer/cart/items')) { window.__e2eCartMutationCalls += 1; window.__e2eLastCartMutationHeaders = Object.fromEntries(new Headers(options.headers||{}).entries()); return json({id:1,status:'active',market_id:1,market_code:'YEM',items:[{id:1,quantity:'1',line_total:'1500',listing}]}); }
    if (url.includes('/marketplace/buyer/cart/items/')) { window.__e2eCartMutationCalls += 1; window.__e2eLastCartMutationHeaders = Object.fromEntries(new Headers(options.headers||{}).entries()); return json({id:1,status:'active',market_id:1,market_code:'YEM',items:[]}); }
    if (url.includes('/marketplace/buyer/addresses') && (options.method||'GET') === 'POST') { const body=JSON.parse(options.body||'{}'); const address={id:20,...body}; window.__e2eAddresses.push(address); window.__e2eAddresses.push({id:21,label:'عنوان بديل',recipient_name:'مشتري الاختبار',phone:'777000000',governorate:body.governorate,city:body.city,address_line:'عنوان آخر',market_id:body.market_id,governorate_id:body.governorate_id,district_id:body.district_id}); return json(address,201); }
    if (url.endsWith('/marketplace/buyer/addresses')) return json({items:window.__e2eAddresses});
    if (url.includes('/platform/market-context/YEM/geography')) { const query=new URL(url,'https://e2e.local').searchParams; const level=query.get('level'); if(level==='governorate') return json({items:[{id:10,code:'YE-TA',level:'governorate',name:'Taiz',name_ar:'تعز',parent_id:1}]}); if(level==='district'&&query.get('parent_id')==='10') return json({items:[{id:20,code:'YE-TA-CAI',level:'district',name:'Al Qahirah',name_ar:'القاهرة',parent_id:10}]}); return json({items:[]}); }
    if (url.includes('/platform/market-context')) return json({items:[{id:1,code:'YEM',locale:'ar-YE'}]});
    if (url.includes('/platform/yemen/checkout-context/YEM')) { window.__e2eCheckoutContextUrl=url; return json({schema_version:'1.0',market:{code:'YEM',locale:'ar-YE'},money:{currency:'YER',label:'ريال يمني',conversion:{automatic_conversion:false}},payments:{methods:[{code:'cod',name:'Cash on delivery',method_type:'cod',requires_provider:false,available:true},{code:'transfer',name:'Manual transfer',method_type:'transfer',requires_provider:true,available:false}],cod:{available:true}},delivery:{destination:{coverage:'available'}},sellers:[{seller_tenant_id:1,delivery:{available:true},payment:{cod_available:true}}]}); }
    if (url.endsWith('/marketplace/buyer/shipping-quotes')) return json({id:301,seller_tenant_id:1,address_id:20,fee:'250',currency:'YER',expires_at:'2099-01-01T00:00:00Z'});
    if (url.endsWith('/marketplace/buyer/checkout')) { window.__e2eCheckoutCalls += 1; window.__e2eLastCheckoutHeaders = Object.fromEntries(new Headers(options.headers||{}).entries()); window.__e2eLastCheckoutBody = JSON.parse(options.body||'{}'); if(window.__e2eLoseFirstCheckoutResponse){window.__e2eLoseFirstCheckoutResponse=false;return Promise.reject(new TypeError('simulated response loss after server acceptance'));} return json({orders:[{id:101,reference:'YEM-E2E-001',currency:'YER',total:'1500'}]}); }
    if (url.endsWith('/marketplace/buyer/customer-orders')) return json({items:[{id:700,reference:'YEM-E2E-001',status:'completed',currency:'YER',subtotal:'1500',shipping_fee:'250',total:'1750',created_at:'2026-11-09T00:00:00Z',seller_orders:[{id:701,seller_tenant_id:1,marketplace_order_id:101,reference:'YEM-E2E-001-S1',status:'fulfilled',subtotal:'1500',shipping_fee:'250',total:'1750',fulfillment:{id:801,method:'external_carrier',status:'delivered',shipment_id:901,carrier:'Yemen Local Delivery',shipment:{id:901,reference:'SHP-E2E-001',carrier:'Yemen Local Delivery',tracking_number:'TRK-E2E-BUYER',status:'delivered',destination:'Taiz'}}}]}]});
    if (url.endsWith('/marketplace/buyer/returns')) return json({items:window.__e2eBuyerReturns});
    if (url.endsWith('/marketplace/platform/disputes')) return json({items:window.__e2eDisputes});
    if (url.match(/\/marketplace\/platform\/disputes\/\d+\/resolve$/) && options.method==='POST') { const id=Number(url.match(/disputes\/(\d+)\/resolve$/)[1]); const body=JSON.parse(options.body||'{}'); const x=window.__e2eDisputes.find(d=>d.id===id); x.status=body.decision; x.resolution=body.resolution; return json({id,status:x.status,resolution:x.resolution}); }
    if (url.match(/\/marketplace\/buyer\/orders\/\d+\/returns$/) && options.method==='POST') { const id=Number(url.match(/orders\/(\d+)\/returns$/)[1]); const body=JSON.parse(options.body||'{}'); const item={id:window.__e2eBuyerReturns.length+1,order_id:id,reason:body.reason,description:body.description,status:'requested'}; window.__e2eBuyerReturns.push(item); return json(item,201); }
    if (url.endsWith('/marketplace/buyer/orders')) return json({items:[{id:101,reference:'YEM-E2E-001',seller_tenant_id:1,total:'1500',currency:'YER',status:'pending_payment',payment_reference:null}]});
    if (url.endsWith('/marketplace/buyer/orders')) return json({items:[{id:101,reference:'YEM-E2E-001',seller_tenant_id:1,total:'1500',currency:'YER',status:'pending_payment',payment_reference:null}]});
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
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM_EXECUTABLE"), args=["--no-sandbox"])
        try:
            for width, height in ((1440, 1000), (390, 844)):
                page = build_page(browser, width, height)
                try:
                    assert page.title() == "Hussam — شبكة التجارة"
                    page.locator("h1", has_text="كل ما تحتاجه، في Hussam.").wait_for(state="visible", timeout=10000)
                    page.locator("text=E2E Phone").wait_for(state="visible", timeout=10000)
                    page.evaluate("window.__e2eOfflineReads=true")
                    page.evaluate("loadPublic()")
                    page.wait_for_timeout(100)
                    assert page.locator("text=E2E Phone").is_visible()
                    page.evaluate("window.__e2eOfflineReads=false")
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
                    page.evaluate("window.__e2eSellerRegistered=false")
                    page.locator("button[data-ws='dashboard']").click()
                    page.locator("#sellerRegistrationForm").wait_for(state="visible", timeout=5000)
                    page.locator("#sellerRegistrationForm input[name='display_name']").fill("متجر تعز")
                    page.locator("#sellerRegistrationForm input[name='slug']").fill("taiz-market")
                    page.locator("#sellerRegistrationForm textarea[name='description']").fill("متجر تجريبي للسوق اليمني")
                    page.locator("#sellerRegistrationForm textarea[name='notes']").fill("نشاط تجاري داخل تعز")
                    page.locator("#sellerRegistrationForm button").click()
                    page.locator("#sellerVerificationForm").wait_for(state="visible", timeout=5000)
                    assert page.evaluate("window.__e2eSellerRegistered") is True
                    assert page.evaluate("window.__e2eSellerVerification") == 'pending'
                    page.locator("button[data-ws='inventory']").click()
                    page.locator("#inventoryItemForm").wait_for(state="visible", timeout=5000)
                    page.locator("#inventoryItemForm input[name='id']").fill("rice-10kg")
                    page.locator("#inventoryItemForm input[name='name']").fill("أرز بسمتي 10 كجم")
                    page.locator("#inventoryItemForm input[name='unit_code']").fill("bag")
                    page.locator("#inventoryItemForm button").click()
                    page.wait_for_function("window.__e2eInventoryRequests.filter(x => x.url.endsWith('/products') && x.method === 'GET').length >= 3", timeout=5000)
                    page.locator("#inventoryWarehouseForm").wait_for(state="visible", timeout=5000)
                    page.locator("#inventoryWarehouseForm input[name='id']").fill("main-warehouse")
                    page.locator("#inventoryWarehouseForm input[name='name']").fill("المستودع الرئيسي")
                    page.locator("#inventoryWarehouseForm button").click()
                    page.wait_for_timeout(250)
                    assert page.evaluate("window.__e2eWarehouses.some(x => x.id === 'main-warehouse')"), f"warehouse POST was not mocked; warehouses={page.evaluate('window.__e2eWarehouses')}; requests={page.evaluate('window.__e2eInventoryRequests')}"
                    page.wait_for_timeout(500)
                    page.wait_for_function("window.__e2eWarehouses.length === 1", timeout=5000)
                    assert page.evaluate("window.__e2eWarehouses[0].id") == "main-warehouse"
                    page.locator("#inventoryMovementForm select[name='item_id'] option[value='rice-10kg']").wait_for(state="attached", timeout=5000)
                    page.locator("#inventoryMovementForm select[name='warehouse_id'] option[value='main-warehouse']").wait_for(state="attached", timeout=5000)
                    page.locator("#inventoryMovementForm select[name='item_id']").select_option("rice-10kg")
                    page.locator("#inventoryMovementForm select[name='warehouse_id']").select_option("main-warehouse")
                    page.locator("#inventoryMovementForm input[name='quantity']").fill("50")
                    page.locator("#inventoryMovementForm input[name='reference']").fill("opening-stock-001")
                    page.locator("#inventoryMovementForm button").click()
                    page.wait_for_function("window.__e2eInventoryRequests.filter(x => x.url.endsWith('/inventory/movements') && x.method === 'GET').length >= 4", timeout=5000)
                    page.locator("#stockLookupForm select[name='item_id']").select_option("rice-10kg")
                    page.locator("#stockLookupForm select[name='warehouse_id']").select_option("main-warehouse")
                    page.locator("#stockLookupForm button").click()
                    page.wait_for_function("document.querySelector('#stockBalance').innerText.includes('50')")
                    page.locator("button[data-ws='products']").click()
                    page.locator("#catalogBundleForm select[name='item_id'] option[value='rice-10kg']").wait_for(state="attached", timeout=5000)
                    page.locator("#catalogBundleForm input[name='name']").fill("أرز بسمتي 10 كجم")
                    page.locator("#catalogBundleForm input[name='product_slug']").fill("basmati-rice-10kg")
                    page.locator("#catalogBundleForm input[name='sku_code']").fill("RICE-10KG")
                    page.locator("#catalogBundleForm select[name='item_id']").select_option("rice-10kg")
                    page.locator("#catalogBundleForm select[name='warehouse_id']").select_option("main-warehouse")
                    page.locator("#catalogBundleForm input[name='unit_price']").fill("2500")
                    page.locator("#catalogBundleForm input[name='currency']").fill("YER")
                    page.locator("#catalogBundleForm input[name='listing_slug']").fill("basmati-rice-10kg")
                    page.locator("#catalogBundleForm button").click()
                    page.locator("small", has_text="basmati-rice-10kg").wait_for(state="visible", timeout=5000)
                    page.evaluate("""window.__e2eSellerOrders=[{id:99,seller_order_id:199,reference:'ORD-E2E-001',buyer_user_id:'buyer-e2e',total:'2500',currency:'YER',status:'pending_payment',payment_method_code:'cod',sales_order_id:501,fulfillment_id:null,fulfillment_status:null,fulfillment_method:null,shipment_id:null,carrier:null,cod_collection_id:null,cod_collection_status:null}]""")
                    page.locator("button[data-ws='orders']").click()
                    page.locator("button[data-processing='99']").click()
                    page.wait_for_function("window.__e2eSellerOrders[0].status === 'processing'")
                    page.locator("button[data-create-fulfillment='199']").wait_for(state="visible", timeout=5000)
                    page.locator("#fulfillment-method-99").select_option("external_carrier")
                    page.locator("button[data-create-fulfillment='199']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='assigned']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='assigned']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='ready']").wait_for(state="visible", timeout=5000)
                    page.locator("input[data-package-ref='701']").fill("PKG-E2E-001")
                    page.locator("button[data-create-package='701']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='ready']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='ready']").click()
                    page.locator("input[data-carrier='701']").fill("Yemen Local Delivery")
                    page.locator("input[data-tracking='701']").fill("TRK-E2E-001")
                    page.locator("button[data-create-shipment='701']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='picked_up']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='picked_up']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='in_transit']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='in_transit']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='out_for_delivery']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='out_for_delivery']").click()
                    page.locator("button[data-fulfillment-transition='701'][data-status='delivered']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-fulfillment-transition='701'][data-status='delivered']").click()
                    page.locator("button[data-collect-cod='701']").wait_for(state="visible", timeout=5000)
                    page.locator("input[data-cod-ref='701']").fill("COD-E2E-001")
                    page.locator("button[data-collect-cod='701']").click()
                    page.wait_for_function("window.__e2eSellerOrders[0].cod_collection_status === 'collected'")
                    assert page.evaluate("window.__e2ePackages.length") == 1
                    assert page.evaluate("window.__e2eCODCollections[0].amount") == "2500"
                    page.evaluate("""window.__e2eReturns=[{id:501,order_id:101,reason:'damaged_item',description:'Damaged packaging',status:'requested',refund_amount:null,refund_currency:null,refund_reference:null,refund_scope:'order',payment_method_code:'card'},{id:502,order_id:102,reason:'damaged_item',description:'COD return',status:'inspected',refund_amount:null,refund_currency:null,refund_reference:null,refund_scope:'order',payment_method_code:'cod'}]""")
                    page.locator("button[data-ws='returns']").click()
                    page.locator("button[data-return-review='501'][data-decision='approved']").wait_for(state="visible", timeout=5000)
                    assert page.locator("button[data-return-refund-approve='502']").count() == 0
                    assert page.locator("text=لا يوجد سجل دفع إلكتروني").is_visible()
                    page.locator("button[data-return-review='501'][data-decision='approved']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='approved'")
                    page.locator("button[data-return-transition='501'][data-status='pickup']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='pickup'")
                    page.locator("button[data-return-transition='501'][data-status='received']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='received'")
                    page.locator("button[data-return-transition='501'][data-status='inspected']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='inspected'")
                    page.locator("button[data-return-refund-approve='501']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='refund_approved'")
                    page.locator("input[data-refund-provider='501']").fill("PROVIDER-REFUND-E2E-001")
                    page.locator("button[data-return-refund-complete='501']").click()
                    page.wait_for_function("window.__e2eReturns[0].status==='refunded'")
                    assert page.evaluate("window.__e2eReturns[0].status") == "refunded"
                    page.locator("button[data-action='home']").click()
                    page.wait_for_timeout(100)
                    page.locator("button[data-add='1']").first.click()
                    page.wait_for_timeout(120)
                    assert page.evaluate("window.__e2eCartMutationCalls") == 1
                    assert page.evaluate("window.__e2eLastCartMutationHeaders['idempotency-key']")
                    page.evaluate("window.dispatchEvent(new Event('offline'))")
                    page.locator("button[data-add='1']").first.click()
                    page.wait_for_timeout(100)
                    assert page.evaluate("window.__e2eCartMutationCalls") == 1
                    assert page.evaluate("JSON.parse(window.__e2eStorage._['hussam_cart_mutation_queue_v1']).length") == 1
                    page.evaluate("window.dispatchEvent(new Event('online'))")
                    page.wait_for_timeout(250)
                    assert page.evaluate("window.__e2eCartMutationCalls") == 2
                    assert page.evaluate("JSON.parse(window.__e2eStorage._['hussam_cart_mutation_queue_v1']).length") == 0
                    page.locator("button[data-action='cart']").click()
                    page.wait_for_timeout(150)
                    page.locator("button[data-action='checkout']:visible").click()
                    page.wait_for_timeout(150)
                    assert page.locator("h1", has_text="إتمام الطلب").is_visible()
                    page.locator("#showAddressForm").click()
                    page.locator("#addressForm input[name='label']").fill("المنزل")
                    page.locator("#addressForm input[name='recipient_name']").fill("مشتري الاختبار")
                    page.locator("#addressForm input[name='phone']").fill("777000000")
                    page.locator("#addressGovernorate").select_option("10")
                    page.locator("#addressDistrict option[value='20']").wait_for(state="attached", timeout=5000)
                    page.locator("#addressDistrict").select_option("20")
                    page.locator("#addressForm textarea[name='address_line']").fill("شارع الاختبار بجوار المعلم")
                    page.locator("#addressForm button").click()
                    page.locator("select[name='shipping_address_id'] option[value='20']").wait_for(state="attached", timeout=5000)
                    assert page.evaluate("window.__e2eAddresses[0].market_id") == 1
                    assert page.evaluate("window.__e2eAddresses[0].governorate_id") == 10
                    assert page.evaluate("window.__e2eAddresses[0].district_id") == 20
                    assert page.locator("text=ريال يمني").is_visible()
                    assert page.locator("text=الدفع عند الاستلام: متاح").is_visible()
                    assert page.locator("text=التوصيل متاح للعنوان المحدد.").is_visible()
                    assert page.locator("option[value='transfer']").is_disabled()
                    assert page.evaluate("window.__e2eCheckoutContextUrl.includes('seller_tenant_ids=1')")
                    page.locator("select[name='shipping_address_id']").select_option("20")
                    page.locator("select[name='payment_method_code']").select_option("cod")
                    page.evaluate("window.dispatchEvent(new Event('offline'))")
                    page.locator("#checkoutForm button").click()
                    page.wait_for_timeout(100)
                    assert page.locator("#notice").is_visible()
                    assert page.evaluate("Object.keys(window.__e2eStorage._).some(k => k.startsWith('hussam_checkout_draft_'))")
                    assert page.evaluate("window.__e2eCheckoutCalls") == 0
                    page.evaluate("window.dispatchEvent(new Event('online'))")
                    page.locator("#checkoutForm button").click()
                    page.wait_for_timeout(150)
                    assert page.evaluate("window.__e2eCheckoutCalls") == 1
                    first_key = page.evaluate("window.__e2eLastCheckoutHeaders['idempotency-key']")
                    page.locator("select[name='shipping_address_id']").select_option("21")
                    page.locator("#checkoutForm button").click()
                    page.wait_for_timeout(100)
                    assert page.evaluate("window.__e2eCheckoutCalls") == 1
                    page.locator("select[name='shipping_address_id']").select_option("20")
                    page.locator("#checkoutForm button").click()
                    page.locator("h2", has_text="YEM-E2E-001").wait_for(state="visible", timeout=10000)
                    assert page.evaluate("window.__e2eCheckoutCalls") == 2
                    assert page.evaluate("window.__e2eLastCheckoutHeaders['idempotency-key']") == first_key
                    assert page.evaluate("window.__e2eLastCheckoutBody.shipping_quote_ids") == [301]
                    assert page.evaluate("window.__e2eLastCheckoutBody.shipping_fee") == 250
                    assert page.locator("text=TRK-E2E-BUYER").is_visible()
                    assert page.locator("text=SHP-E2E-001").is_visible()
                    page.locator("details.return-request summary").click()
                    page.locator("input[data-buyer-return-reason='101']").fill("منتج تالف")
                    page.locator("textarea[data-buyer-return-description='101']").fill("وصل المنتج متضرراً")
                    page.locator("button[data-buyer-return='101']").click()
                    page.wait_for_function("window.__e2eBuyerReturns.length===1")
                    assert page.evaluate("window.__e2eBuyerReturns[0].status") == "requested"
                    page.evaluate("""window.__e2eDisputes=[{id:900,order_id:101,opened_by_user_id:'buyer-e2e',reason:'item_not_as_described',description:'Product differs from listing',status:'open',resolution:null}]""")
                    page.locator("button[data-action='account']").click()
                    page.locator("button[data-action='admin']").wait_for(state="visible", timeout=5000)
                    page.locator("button[data-action='admin']").click()
                    page.locator("button[data-ws='trust']").click()
                    page.locator("button[data-dispute-resolve='900']").wait_for(state="visible", timeout=5000)
                    page.locator("select[data-dispute-decision='900']").select_option("resolved")
                    page.locator("textarea[data-dispute-resolution='900']").fill("تمت مراجعة الأدلة والتوصل إلى حل")
                    page.locator("button[data-dispute-resolve='900']").click()
                    page.wait_for_function("window.__e2eDisputes[0].status==='resolved'")
                    assert page.evaluate("window.__e2eDisputes[0].resolution") == "تمت مراجعة الأدلة والتوصل إلى حل"
                finally:
                    page.close()
        finally:
            browser.close()
    print("BROWSER_E2E_OK desktop+mobile")


if __name__ == "__main__":
    run()
