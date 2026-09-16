from sqlalchemy.orm import Session
from app.core.contracts import StockMovement
from app.core.models import InventoryMovementRecord
from app.engines.inventory.service import InventoryService
class InventoryPersistenceService:
    def __init__(self, db: Session): self.db = db
    def record(self, tenant_id: int, movement: StockMovement) -> InventoryMovementRecord:
        InventoryService().validate_movement(movement)
        r = InventoryMovementRecord(tenant_id=tenant_id, item_id=movement.item_id, warehouse_id=movement.warehouse_id, quantity=movement.quantity, direction=movement.direction, reference=movement.reference)
        self.db.add(r); self.db.commit(); self.db.refresh(r); return r
