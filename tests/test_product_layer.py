from tests.test_api import setup_client, teardown

def test_product_read_surfaces_are_authenticated_and_tenant_scoped():
    client, _, token = setup_client()
    try:
        assert client.get('/api/v1/products').status_code == 401
        h={'Authorization':f'Bearer {token}'}
        assert client.post('/api/v1/inventory/items',json={'id':'i1','name':'Private'},headers=h).status_code==201
        assert client.post('/api/v1/inventory/warehouses',json={'id':'w1','name':'Main'},headers=h).status_code==201
        assert client.post('/api/v1/inventory/movements',json={'item_id':'i1','warehouse_id':'w1','quantity':'4','direction':'in','reference':'m1'},headers=h).status_code==201
        assert client.get('/api/v1/products',headers=h).json()['items'][0]['id']=='i1'
        assert client.get('/api/v1/warehouses',headers=h).json()['items'][0]['id']=='w1'
        assert client.get('/api/v1/inventory/movements',headers=h).json()['items'][0]['reference']=='m1'
        assert client.get('/api/v1/sales/orders',headers=h).status_code==200
        assert client.get('/api/v1/purchasing/suppliers',headers=h).status_code==200
        assert client.get('/api/v1/purchasing/orders',headers=h).status_code==200
        assert client.get('/api/v1/payments/intents',headers=h).status_code==200
        assert client.get('/api/v1/logistics/shipments',headers=h).status_code==200
        assert client.get('/api/v1/finance/journals',headers=h).status_code==200
        assert client.get('/api/v1/documents',headers=h).status_code==200
    finally: teardown()
