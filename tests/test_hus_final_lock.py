import pytest
from app.hus.compiler import compile_source, HUSCompileError
from app.hus.release import evaluate_ir
from app.hus.runtime import SovereignRuntime, HUSRuntimeError
from app.hus.bindings import build_production_bindings
from app.core.persistence import Base
from app.core.models.ai_hus import HUSCompilation
from app.core.models.amazon_completion import HUSExecutionRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

SOURCE = """module shop version \"1.0\" {
 organization code = shop name = \"Shop\";
 domain retail { engine = retail; capabilities = [catalog.read]; name = \"Retail\"; enabled = true; }
 workflow inspect { trigger = inventory.changed; step read { action = retail.catalog.read; } }
}
"""

def test_final_language_compile_is_deterministic():
    a=compile_source(SOURCE); b=compile_source(SOURCE)
    assert a['ast_hash']==b['ast_hash']==a['source_hash']
    assert a['execution_plan_hash']==b['execution_plan_hash']

def test_final_release_gate_passes():
    r=compile_source(SOURCE)
    from app.hus.parser import parse
    from app.hus.semantic import validate_ast
    from app.hus.planner import build_ir
    report=evaluate_ir(build_ir(validate_ast(parse(SOURCE))))
    assert report.passed

def test_source_rejects_unsafe_unknown_capability():
    with pytest.raises(HUSCompileError):
        compile_source(SOURCE.replace('retail.catalog.read','retail.shell.exec'))

def test_runtime_failure_rolls_back_domain_transaction():
    e=create_engine('sqlite+pysqlite:///:memory:', future=True); Base.metadata.create_all(e); db=sessionmaker(e, expire_on_commit=False)()
    c=HUSCompilation(id='c',tenant_id=1,actor_id='u',spec_version='1.0',source_hash='s'*64,contract_hash='p'*64,status='active',contract={'execution_plan':{'workflows':[{'code':'w','steps':[{'id':'w.s','action':{'engine':'commerce','capability':'sales.create'},'risk':'mutation','idempotency_required':True}]}]}})
    db.add(c); db.commit(); r=SovereignRuntime(db)
    def failing(db,ctx,args):
        raise RuntimeError('boom')
    r.register_mutation_handler('commerce.sales.create',failing)
    with pytest.raises(HUSRuntimeError, match='failed'):
        r.execute_step(1,'u','c','w.s',{},approval_ref='a',approved=True,idempotency_key='idem')
    rows=db.scalars(select(HUSExecutionRecord).where(HUSExecutionRecord.compilation_id=='c')).all()
    assert len(rows)==1 and rows[0].status=='failed'

def test_runtime_never_executes_registered_capability_without_binding():
    e=create_engine('sqlite+pysqlite:///:memory:', future=True); Base.metadata.create_all(e); db=sessionmaker(e, expire_on_commit=False)()
    c=HUSCompilation(id='c',tenant_id=1,actor_id='u',spec_version='1.0',source_hash='s'*64,contract_hash='p'*64,status='active',contract={'execution_plan':{'workflows':[{'code':'w','steps':[{'id':'w.s','action':{'engine':'finance','capability':'finance.read'},'risk':'read'}]}]}})
    db.add(c); db.commit(); r=SovereignRuntime(db)
    with pytest.raises(HUSRuntimeError, match='no sovereign runtime handler'):
        r.execute_step(1,'u','c','w.s',{})
