from app.core.contracts import StockMovement
class InventoryInvariantError(ValueError):
    pass
class InventoryService:
    def validate_movement(self, movement: StockMovement) -> None:
        if movement.quantity <= 0: raise InventoryInvariantError('quantity must be positive')
        if movement.direction not in {'in','out','transfer'}: raise InventoryInvariantError('unsupported movement direction')
        if not movement.item_id or not movement.warehouse_id or not movement.reference: raise InventoryInvariantError('item, warehouse and reference are required')
        if movement.direction == 'transfer' and not movement.destination_warehouse_id: raise InventoryInvariantError('transfer destination is required')
