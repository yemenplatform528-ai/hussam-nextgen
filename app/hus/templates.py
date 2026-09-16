"""Safe, declarative HUS starter specifications for platform verticals."""

def retail_marketplace_spec(organization_code: str, organization_name: str) -> dict:
    return {
        'spec_version':'1.0',
        'organization':{'code':organization_code,'name':organization_name},
        'domains':[
            {'code':'retail','name':'Retail','engine':'retail','enabled':True,'capabilities':['catalog.read','catalog.write','register.open','register.close']},
            {'code':'inventory','name':'Inventory','engine':'inventory','enabled':True,'capabilities':['inventory.read','inventory.receive','inventory.issue','inventory.reserve']},
            {'code':'commerce','name':'Commerce','engine':'commerce','enabled':True,'capabilities':['sales.read','sales.create','sales.confirm','sales.fulfill']},
            {'code':'payments','name':'Payments','engine':'payments','enabled':True,'capabilities':['payments.read','payments.create','payments.capture','payments.settle']},
            {'code':'logistics','name':'Logistics','engine':'logistics','enabled':True,'capabilities':['logistics.read','logistics.create','logistics.deliver']},
            {'code':'marketplace','name':'Marketplace','engine':'marketplace','enabled':True,'capabilities':['marketplace.read','marketplace.seller','marketplace.catalog','marketplace.order','marketplace.payout','marketplace.moderate']},
        ],
        'workflows':[
            {'code':'marketplace_order','name':'Marketplace Order','trigger':'marketplace.order.created','steps':[
                {'code':'confirm_sale','action':'commerce.sales.confirm','requires_approval':False},
                {'code':'capture_payment','action':'payments.capture','requires_approval':True},
                {'code':'deliver','action':'logistics.deliver','requires_approval':False},
            ],'enabled':True}
        ],
        'policies':{'approval_required':['payments.capture','marketplace.payout'],'allowed_roles':['owner','admin']},
        'metadata':{'template':'retail-marketplace','version':'1.0'},
    }
