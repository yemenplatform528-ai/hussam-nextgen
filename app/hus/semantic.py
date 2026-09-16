"""HUS-01 semantic validation: names, capabilities and closed type rules."""
from .ast import ModuleAST
from .registry import ENGINE_CAPABILITIES, capabilities_for
from .compiler import Diagnostic, HUSCompileError

def validate_ast(ast: ModuleAST):
    d=[]
    if ast.version != '1.0': d.append(Diagnostic('Semantic','unsupported_language_version','language version must be 1.0'))
    if not ast.name: d.append(Diagnostic('Semantic','module_name_required','module name is required'))
    dc=set()
    for x in ast.domains:
        if x.code in dc: d.append(Diagnostic('Semantic','duplicate_domain',f'duplicate domain: {x.code}'))
        dc.add(x.code)
        if x.engine not in ENGINE_CAPABILITIES: d.append(Diagnostic('Semantic','unsupported_engine',f'unsupported engine: {x.engine}'))
        for cap in x.capabilities:
            if cap not in capabilities_for(x.engine): d.append(Diagnostic('Semantic','unsupported_capability',f'capability {cap} is not allowed for engine {x.engine}'))
    wc=set()
    for w in ast.workflows:
        if w.code in wc: d.append(Diagnostic('Semantic','duplicate_workflow',f'duplicate workflow: {w.code}'))
        wc.add(w.code); sc=set()
        for s in w.steps:
            if s.code in sc: d.append(Diagnostic('Semantic','duplicate_step',f'duplicate step {s.code} in workflow {w.code}'))
            sc.add(s.code)
            if '.' not in s.action: d.append(Diagnostic('Semantic','action_format','action must use engine.capability form'))
            else:
                engine,cap=s.action.split('.',1)
                if engine not in ENGINE_CAPABILITIES: d.append(Diagnostic('Semantic','action_engine_unknown',f'unknown action engine: {engine}'))
                elif not any(c==cap or c.endswith('.'+cap) for c in capabilities_for(engine)):
                    d.append(Diagnostic('Semantic','action_not_allowed',f'action {s.action} is not registered for engine {engine}'))
    policy_names={'approval_required','allowed_roles'}
    for p in ast.policies:
        if p.name not in policy_names: d.append(Diagnostic('Semantic','unknown_policy',f'unsupported policy: {p.name}'))
    if d: raise HUSCompileError(d)
    return ast
