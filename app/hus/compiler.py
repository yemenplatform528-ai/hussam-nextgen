"""Deterministic HUS operational compiler. No code execution, imports, shell, or network access."""
from dataclasses import dataclass
from hashlib import sha256
import json
from .registry import capabilities_for, ENGINE_CAPABILITIES

STAGES = ('Boot','Parser','Validator','Resolver','Contract Injector','Generator')
ALLOWED_ROOT = {'spec_version','organization','domains','workflows','policies','metadata'}
ALLOWED_DOMAIN = {'code','name','engine','enabled','capabilities'}
ALLOWED_WORKFLOW = {'code','name','trigger','steps','enabled'}
ALLOWED_STEP = {'code','action','requires_approval'}
ALLOWED_RISKS = {'read','mutation','admin'}
ALLOWED_POLICY = {'approval_required','allowed_roles'}

@dataclass(frozen=True)
class Diagnostic:
    stage: str
    code: str
    message: str

class HUSCompileError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__(json.dumps([d.__dict__ for d in diagnostics], ensure_ascii=False, sort_keys=True))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def _diag(diags, stage, code, message):
    diags.append(Diagnostic(stage, code, message))

def compile_spec(source: dict) -> dict:
    d=[]
    if not isinstance(source, dict):
        raise HUSCompileError([Diagnostic('Boot','spec_object_required','specification must be an object')])
    unknown=set(source)-ALLOWED_ROOT
    for x in sorted(unknown): _diag(d,'Validator','unknown_root_key',f'unsupported root key: {x}')
    if source.get('spec_version') != '1.0': _diag(d,'Validator','unsupported_spec_version','spec_version must be 1.0')
    org=source.get('organization')
    if not isinstance(org,dict) or not org.get('code') or not org.get('name'):
        _diag(d,'Validator','organization_required','organization.code and organization.name are required')
    domains=source.get('domains',[])
    if not isinstance(domains,list): _diag(d,'Validator','domains_array','domains must be an array'); domains=[]
    domain_codes=set()
    for item in domains:
        if not isinstance(item,dict): _diag(d,'Validator','domain_object','each domain must be an object'); continue
        for x in sorted(set(item)-ALLOWED_DOMAIN): _diag(d,'Validator','unknown_domain_key',f'unsupported domain key: {x}')
        code=item.get('code'); engine=item.get('engine')
        if not code: _diag(d,'Validator','domain_code_required','domain.code is required')
        elif code in domain_codes: _diag(d,'Validator','duplicate_domain',f'duplicate domain: {code}')
        else: domain_codes.add(code)
        if engine not in ENGINE_CAPABILITIES: _diag(d,'Resolver','unsupported_engine',f'unsupported engine for domain {code}: {engine}')
        caps=item.get('capabilities',[])
        if not isinstance(caps,list) or any(not isinstance(c,str) for c in caps): _diag(d,'Validator','capabilities_array',f'domain {code} capabilities must be an array of strings'); caps=[]
        for cap in caps:
            if cap not in capabilities_for(engine): _diag(d,'Resolver','unsupported_capability',f'capability {cap} is not allowed for engine {engine}')
    workflows=source.get('workflows',[])
    if not isinstance(workflows,list): _diag(d,'Validator','workflows_array','workflows must be an array'); workflows=[]
    workflow_codes=set()
    for w in workflows:
        if not isinstance(w,dict): _diag(d,'Validator','workflow_object','each workflow must be an object'); continue
        for x in sorted(set(w)-ALLOWED_WORKFLOW): _diag(d,'Validator','unknown_workflow_key',f'unsupported workflow key: {x}')
        code=w.get('code')
        if not code: _diag(d,'Validator','workflow_code_required','workflow.code is required')
        elif code in workflow_codes: _diag(d,'Validator','duplicate_workflow',f'duplicate workflow: {code}')
        else: workflow_codes.add(code)
        steps=w.get('steps',[])
        if not isinstance(steps,list) or not steps: _diag(d,'Validator','workflow_steps_required',f'workflow {code} needs steps'); continue
        step_codes=set()
        for s in steps:
            if not isinstance(s,dict): _diag(d,'Validator','step_invalid',f'workflow {code} contains an invalid step'); continue
            for x in sorted(set(s)-ALLOWED_STEP): _diag(d,'Validator','unknown_step_key',f'unsupported step key: {x}')
            sc=s.get('code'); action=s.get('action')
            if not sc or not action: _diag(d,'Validator','step_invalid',f'workflow {code} contains an invalid step')
            elif sc in step_codes: _diag(d,'Validator','duplicate_step',f'duplicate step {sc} in workflow {code}')
            else: step_codes.add(sc)
            if action and '.' not in action: _diag(d,'Resolver','action_format','workflow action must use engine.action form')
            if action and '.' in action:
                engine, capability = action.split('.',1)
                if engine not in ENGINE_CAPABILITIES: _diag(d,'Resolver','action_engine_unknown',f'unknown action engine: {engine}')
                elif not any(cap == capability or cap.endswith('.'+capability) for cap in capabilities_for(engine)):
                    _diag(d,'Resolver','action_not_allowed',f'action {action} is not registered for engine {engine}')
    policies=source.get('policies',{})
    if not isinstance(policies,dict): _diag(d,'Validator','policies_object','policies must be an object'); policies={}
    for key in policies:
        if key not in ALLOWED_POLICY: _diag(d,'Validator','unknown_policy',f'unsupported policy: {key}')
    if 'approval_required' in policies and not isinstance(policies['approval_required'],list): _diag(d,'Validator','approval_policy_array','approval_required must be an array')
    if 'allowed_roles' in policies and not isinstance(policies['allowed_roles'],list): _diag(d,'Validator','allowed_roles_array','allowed_roles must be an array')
    if d: raise HUSCompileError(d)

    resolved_domains=[]
    for x in domains:
        resolved_domains.append({'code':x['code'],'name':x.get('name',x['code']),'engine':x['engine'],'enabled':bool(x.get('enabled',True)),'capabilities':sorted(set(x.get('capabilities',[])))})
    resolved_workflows=[]
    for w in workflows:
        resolved_workflows.append({'code':w['code'],'name':w.get('name',w['code']),'trigger':w.get('trigger'),'enabled':bool(w.get('enabled',True)),'steps':[{'code':s['code'],'action':s['action'],'requires_approval':bool(s.get('requires_approval',False))} for s in w['steps']]})
    contract={
        'contract_version':'1.1',
        'organization': {'code':org['code'],'name':org['name']},
        'domains': sorted(resolved_domains,key=lambda x:x['code']),
        'workflows': sorted(resolved_workflows,key=lambda x:x['code']),
        'policies': json.loads(canonical(policies)),
        'metadata': json.loads(canonical(source.get('metadata',{}))) if isinstance(source.get('metadata',{}),dict) else {},
    }
    # Contract Injector: only declarative command/read bindings from the allow-listed registry.
    bindings=[]
    for x in contract['domains']:
        if x['enabled']:
            for cap in x['capabilities']: bindings.append({'domain':x['code'],'capability':cap})
    contract['bindings']=sorted(bindings,key=lambda x:(x['domain'],x['capability']))
    payload=canonical(contract)
    return {'stages':list(STAGES),'contract':contract,'source_hash':sha256(canonical(source).encode()).hexdigest(),'contract_hash':sha256(payload.encode()).hexdigest()}

# HUS-01 source-language front-end. Kept separate from the legacy dict contract for compatibility.
def compile_source(source: str) -> dict:
    from .parser import parse
    from .semantic import validate_ast
    from .lowering import ast_to_spec, canonical_ast
    ast = validate_ast(parse(source))
    spec = ast_to_spec(ast)
    result = compile_spec(spec)
    result['language_version'] = ast.version
    result['module'] = ast.name
    result['ast'] = canonical_ast(ast)
    result['ast_hash'] = sha256(result['ast'].encode()).hexdigest()
    result['source_hash'] = sha256(result['ast'].encode()).hexdigest()
    from .planner import build_ir, canonical_ir, plan_hash, validate_ir
    ir = build_ir(ast)
    validate_ir(ir)
    result['ir'] = json.loads(canonical_ir(ir))
    result['ir_hash'] = plan_hash(ir)
    result['execution_plan'] = result['ir']
    result['execution_plan_hash'] = result['ir_hash']
    return result
