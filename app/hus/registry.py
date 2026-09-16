"""Allow-listed HUS engine/capability registry. Declarative only; no executable hooks."""
ENGINE_CAPABILITIES = {
    'retail': {'catalog.read','catalog.write','register.open','register.close'},
    'inventory': {'inventory.read','inventory.receive','inventory.issue','inventory.transfer','inventory.reserve'},
    'commerce': {'sales.read','sales.create','sales.confirm','sales.fulfill','sales.cancel'},
    'procurement': {'purchasing.read','purchasing.create','purchasing.confirm','purchasing.receive','purchasing.cancel'},
    'payments': {'payments.read','payments.create','payments.capture','payments.settle','payments.reconcile'},
    'logistics': {'logistics.read','logistics.create','logistics.pickup','logistics.deliver','logistics.cancel'},
    'finance': {'finance.read','finance.post','finance.reverse'},
    'workflow': {'workflow.read','workflow.start','workflow.transition','workflow.cancel'},
    'documents': {'documents.read','documents.create','documents.finalize','documents.void'},
    'marketplace': {'marketplace.read','marketplace.seller','marketplace.catalog','marketplace.order','marketplace.payout','marketplace.moderate'},
    'custom': set(),
}

def capabilities_for(engine: str):
    return ENGINE_CAPABILITIES.get(engine, set())
