from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.models.marketplace import MarketplaceFulfillment, MarketplaceSellerOrder, MarketplaceOrder, MarketplaceCustomerOrder, MarketplaceAddress, MarketplacePackage
from app.core.models.logistics import Shipment, ShipmentEvent
from app.core.models.commerce import SalesOrder
from app.engines.commerce import CommerceProductionService
from app.engines.logistics import LogisticsProductionService

class FulfillmentError(ValueError):
    pass

_ALLOWED = {
    'pending': {'assigned','cancelled'},
    'assigned': {'ready','cancelled'},
    'ready': {'picked_up','delivered','cancelled'},
    'picked_up': {'in_transit','out_for_delivery','delivered','failed','returned'},
    'in_transit': {'out_for_delivery','delivered','failed','returned'},
    'out_for_delivery': {'delivered','failed','returned'},
    'delivered': set(), 'failed': {'ready','cancelled','returned'}, 'returned': set(), 'cancelled': set(),
}

class FulfillmentService:
    def __init__(self, db): self.db = db

    def _seller_order(self, seller_tenant_id, seller_order_id, lock=False):
        q = select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.id == seller_order_id, MarketplaceSellerOrder.seller_tenant_id == seller_tenant_id)
        if lock: q = q.with_for_update()
        x = self.db.scalar(q)
        if not x: raise FulfillmentError('seller order not found in seller tenant')
        return x

    def _fulfillment(self, seller_tenant_id, fulfillment_id, lock=False):
        q = select(MarketplaceFulfillment).where(MarketplaceFulfillment.id == fulfillment_id, MarketplaceFulfillment.seller_tenant_id == seller_tenant_id)
        if lock: q = q.with_for_update()
        x = self.db.scalar(q)
        if not x: raise FulfillmentError('fulfillment not found in seller tenant')
        return x

    def create(self, seller_tenant_id, seller_order_id, method='seller_fulfilled'):
        if method not in {'seller_fulfilled','hussam_delivery','external_carrier','pickup'}: raise FulfillmentError('unsupported fulfillment method')
        so = self._seller_order(seller_tenant_id, seller_order_id, True)
        if so.status not in {'processing','ready_for_fulfillment'}: raise FulfillmentError('seller order must be processing before fulfillment')
        active = self.db.scalar(select(MarketplaceFulfillment).where(MarketplaceFulfillment.seller_order_id==so.id, MarketplaceFulfillment.status.not_in({'delivered','returned','cancelled'})))
        if active:
            if active.status != 'pending': raise FulfillmentError('seller order already has an active fulfillment')
            active.method=method; active.updated_at=datetime.now(timezone.utc); self.db.commit(); self.db.refresh(active); return active
        f = MarketplaceFulfillment(seller_order_id=so.id,seller_tenant_id=seller_tenant_id,method=method,status='pending')
        self.db.add(f); so.status='ready_for_fulfillment'; so.updated_at=datetime.now(timezone.utc); self.db.flush()
        self.db.commit(); self.db.refresh(f); return f

    def transition(self, seller_tenant_id, fulfillment_id, status, event_id=None, location=None, note=None):
        if status not in _ALLOWED: raise FulfillmentError('unsupported fulfillment status')
        f = self._fulfillment(seller_tenant_id, fulfillment_id, True)
        if event_id is None: event_id = f'FUL:{f.id}:{status}:{uuid4().hex[:12]}'
        # The logistics layer owns physical shipment state and event idempotency.
        # Fulfillment mirrors it; it must never create a second shipment event for
        # the same carrier/webhook event.
        if status not in _ALLOWED[f.status]:
            existing = self.db.scalar(select(ShipmentEvent).where(ShipmentEvent.tenant_id == seller_tenant_id, ShipmentEvent.event_id == event_id))
            if existing and existing.shipment_id == f.shipment_id:
                return f
            raise FulfillmentError(f'invalid fulfillment transition: {f.status} -> {status}')
        so = self._seller_order(seller_tenant_id, f.seller_order_id, True)
        if so.status not in {'processing','ready_for_fulfillment'}:
            raise FulfillmentError('seller order must be processing or ready_for_fulfillment for fulfillment transition')
        if status in {'picked_up','in_transit','out_for_delivery','delivered'} and f.method != 'pickup' and not f.shipment_id:
            raise FulfillmentError('shipment is required before physical delivery transition')
        if status == 'delivered' and f.method == 'pickup' and not note:
            raise FulfillmentError('pickup delivery requires a collection note')
        if f.method != 'pickup' and f.shipment_id and status in {'picked_up','in_transit','out_for_delivery','delivered'}:
            try:
                LogisticsProductionService(self.db).transition(
                    seller_tenant_id, f.shipment_id, status, event_id=event_id,
                    location=location, note=note
                )
            except Exception as exc:
                raise FulfillmentError(str(exc)) from exc
        f.status=status; f.updated_at=datetime.now(timezone.utc)
        if status == 'assigned': f.assigned_at=datetime.now(timezone.utc)
        if status in {'assigned','ready','picked_up','in_transit','out_for_delivery'}: so.status='ready_for_fulfillment'
        if status == 'delivered': so.status='fulfilled'
        self.db.commit()
        # Re-sync the customer-facing aggregate using the existing marketplace authority.
        from app.engines.marketplace import MarketplaceService
        MarketplaceService(self.db)._sync_customer_order(self.db.scalar(select(MarketplaceOrder.customer_order_id).where(MarketplaceOrder.id==so.marketplace_order_id)))
        self.db.commit(); return f

    def create_package(self, seller_tenant_id, fulfillment_id, reference, weight_kg=None, notes=''):
        f=self._fulfillment(seller_tenant_id,fulfillment_id,True)
        if f.status not in {'assigned','ready'}: raise FulfillmentError('package can only be created after fulfillment assignment')
        if not reference: raise FulfillmentError('package reference is required')
        if weight_kg is not None and Decimal(str(weight_kg)) <= 0: raise FulfillmentError('package weight must be positive')
        if self.db.scalar(select(MarketplacePackage).where(MarketplacePackage.seller_tenant_id==seller_tenant_id,MarketplacePackage.reference==reference)):
            raise FulfillmentError('duplicate package reference')
        p=MarketplacePackage(fulfillment_id=f.id,seller_tenant_id=seller_tenant_id,reference=reference,status='packed',weight_kg=weight_kg,notes=notes or '')
        self.db.add(p)
        try:
            self.db.commit(); self.db.refresh(p); return p
        except IntegrityError:
            self.db.rollback(); raise FulfillmentError('duplicate package reference')

    def create_shipment(self, seller_tenant_id, fulfillment_id, carrier, tracking_number=None):
        f = self._fulfillment(seller_tenant_id, fulfillment_id, True)
        if f.status not in {'ready','assigned'}: raise FulfillmentError('fulfillment must be assigned or ready before shipment creation')
        if f.method == 'pickup': raise FulfillmentError('pickup fulfillment does not use a shipment')
        so = self._seller_order(seller_tenant_id, f.seller_order_id, True)
        mo = self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==so.marketplace_order_id, MarketplaceOrder.seller_tenant_id==seller_tenant_id))
        if not mo or not mo.sales_order_id: raise FulfillmentError('seller order has no commerce shipment linkage')
        sales = self.db.scalar(select(SalesOrder).where(SalesOrder.id==mo.sales_order_id, SalesOrder.tenant_id==seller_tenant_id).with_for_update())
        if not sales: raise FulfillmentError('sales order not found in seller tenant')
        if sales.status == 'confirmed': CommerceProductionService(self.db).fulfill(seller_tenant_id, sales.id); sales = self.db.scalar(select(SalesOrder).where(SalesOrder.id==sales.id))
        if sales.status != 'fulfilled': raise FulfillmentError('commerce order must be fulfilled before shipment')
        address = self.db.scalar(select(MarketplaceAddress).join(MarketplaceCustomerOrder, MarketplaceCustomerOrder.shipping_address_id==MarketplaceAddress.id).where(MarketplaceCustomerOrder.id==mo.customer_order_id, MarketplaceAddress.user_id==mo.buyer_user_id))
        if not address: raise FulfillmentError('customer shipping address is required')
        destination = f'{address.recipient_name}, {address.phone}, {address.governorate}, {address.city}, {address.address_line}' + (f', {address.landmark}' if address.landmark else '')
        ref=f'SHP-{mo.reference}-{f.id}'
        shipment = LogisticsProductionService(self.db).create_shipment(seller_tenant_id, order_id=mo.sales_order_id, reference=ref, origin_warehouse_id=sales.warehouse_id, destination=destination, carrier=carrier, currency=mo.currency, cod_amount=Decimal('0'), tracking_number=tracking_number)
        f.shipment_id=shipment.id; f.carrier=carrier; f.status='ready'; f.updated_at=datetime.now(timezone.utc); self.db.commit(); self.db.refresh(f); return f, shipment
