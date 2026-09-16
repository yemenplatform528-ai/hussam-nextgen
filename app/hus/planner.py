"""HUS-02 semantic lowering: AST/contract -> deterministic typed IR and bounded plan."""
from hashlib import sha256
import json
from .ast import ModuleAST
from .ir import HUSIR, IRWorkflow, IRStep, CapabilityRef
from .registry import capabilities_for

COMPILER_VERSION = "hus-compiler-2.0"
IR_VERSION = "1.0"
MAX_STEPS = 128
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 300
DEFAULT_RETRIES = 0
MAX_RETRIES = 3

READ_CAPABILITIES = {"read"}

def _split(action: str):
    engine, cap = action.split('.', 1)
    return engine, cap

def _risk(action: str) -> str:
    _, cap = _split(action)
    if cap.endswith('.read') or cap == 'read': return 'read'
    if cap in {'moderate','admin'}: return cap
    return 'mutation'

def _id(workflow: str, step: str) -> str:
    return f"{workflow}.{step}"

def build_ir(ast: ModuleAST) -> HUSIR:
    workflows=[]
    refs={}
    for w in sorted(ast.workflows, key=lambda x: x.code):
        if len(w.steps) > MAX_STEPS:
            raise ValueError(f"workflow {w.code} exceeds HUS plan step limit {MAX_STEPS}")
        steps=[]
        previous=None
        for s in w.steps:
            engine, cap = _split(s.action)
            from .registry import ENGINE_CAPABILITIES
            if engine not in ENGINE_CAPABILITIES:
                raise ValueError(f"unregistered HUS engine: {engine}")
            allowed = capabilities_for(engine)
            if not any(c == cap or c.endswith('.'+cap) for c in allowed):
                raise ValueError(f"unregistered HUS capability: {s.action}")
            ref=CapabilityRef(engine, cap)
            refs[(engine,cap)] = ref
            risk=_risk(s.action)
            steps.append(IRStep(
                id=_id(w.code,s.code), action=ref,
                depends_on=(previous,) if previous else (),
                requires_approval=bool(s.requires_approval or risk != 'read'),
                risk=risk,
                timeout_seconds=DEFAULT_TIMEOUT,
                retry_limit=DEFAULT_RETRIES,
                idempotency_required=risk != 'read',
                compensation=None,
            ))
            previous=_id(w.code,s.code)
        workflows.append(IRWorkflow(w.code,w.trigger,tuple(steps)))
    return HUSIR(IR_VERSION, ast.version, COMPILER_VERSION,
                  tuple(refs[k] for k in sorted(refs)), tuple(workflows))

def canonical_ir(ir: HUSIR) -> str:
    value={
        'ir_version':ir.ir_version,
        'language_version':ir.language_version,
        'compiler_version':ir.compiler_version,
        'capabilities':[{'engine':x.engine,'capability':x.capability,'contract_version':x.contract_version} for x in ir.capabilities],
        'workflows':[{'code':w.code,'trigger':w.trigger,'steps':[{
            'id':s.id,'action':{'engine':s.action.engine,'capability':s.action.capability,'contract_version':s.action.contract_version},
            'depends_on':list(s.depends_on),'requires_approval':s.requires_approval,'risk':s.risk,
            'timeout_seconds':s.timeout_seconds,'retry_limit':s.retry_limit,
            'idempotency_required':s.idempotency_required,'compensation':s.compensation
        } for s in w.steps]} for w in ir.workflows]
    }
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def plan_hash(ir: HUSIR) -> str:
    return sha256(canonical_ir(ir).encode()).hexdigest()

def validate_ir(ir: HUSIR):
    seen=set()
    for w in ir.workflows:
        previous=set()
        for s in w.steps:
            if s.id in seen: raise ValueError(f'duplicate IR step: {s.id}')
            seen.add(s.id)
            if s.timeout_seconds < 1 or s.timeout_seconds > MAX_TIMEOUT: raise ValueError('IR timeout out of bounds')
            if s.retry_limit < 0 or s.retry_limit > MAX_RETRIES: raise ValueError('IR retry limit out of bounds')
            if any(dep not in previous for dep in s.depends_on): raise ValueError('IR dependency must reference an earlier step')
            previous.add(s.id)
            if s.risk != 'read' and not s.idempotency_required: raise ValueError('mutation IR step requires idempotency')
    return True
