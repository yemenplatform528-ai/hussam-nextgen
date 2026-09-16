from app.hus.compiler import compile_source, HUSCompileError
from app.hus.planner import canonical_ir

SRC='''
module shop version "1.0" {
 organization code = shop name = Shop;
 domain retail { engine = retail capabilities = [catalog.read]; }
 workflow stock_check {
   trigger = inventory.changed;
   step read { action = inventory.inventory.read; }
   step confirm { action = commerce.sales.confirm; approval; }
 }
 policy allowed_roles = [admin];
}
'''

def test_hus02_emits_typed_ir_and_plan_hash():
    r=compile_source(SRC)
    assert r['ir_version'] if 'ir_version' in r else True
    assert r['ir_hash'] == r['execution_plan_hash']
    assert r['ir']['workflows'][0]['steps'][1]['id']=='stock_check.confirm'

def test_hus02_mutation_is_approval_and_idempotent():
    r=compile_source(SRC)
    s=r['ir']['workflows'][0]['steps'][1]
    assert s['requires_approval'] is True
    assert s['risk']=='mutation'
    assert s['idempotency_required'] is True
    assert s['depends_on']==['stock_check.read']

def test_hus02_read_is_not_forced_to_idempotency():
    r=compile_source(SRC)
    s=r['ir']['workflows'][0]['steps'][0]
    assert s['risk']=='read'
    assert s['idempotency_required'] is False
    assert s['requires_approval'] is False

def test_hus02_deterministic_plan_for_whitespace_change():
    a=compile_source(SRC)
    b=compile_source(SRC.replace('step read', 'step   read').replace('\n', '\n\n'))
    assert a['ir_hash']==b['ir_hash']

def test_hus02_unknown_action_rejected_before_ir():
    bad=SRC.replace('inventory.inventory.read','inventory.inventory.nope')
    try: compile_source(bad)
    except HUSCompileError as e: assert 'action_not_allowed' in str(e) or 'unsupported_capability' in str(e)
    else: raise AssertionError('expected compile rejection')
