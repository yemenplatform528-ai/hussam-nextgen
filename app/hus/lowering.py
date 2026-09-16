"""Pure AST -> canonical legacy contract input. No execution or I/O."""
import json
from dataclasses import asdict
from .ast import ModuleAST

def _value(v): return {'kind':v.kind,'value':v.value}

def ast_to_spec(ast: ModuleAST) -> dict:
    policies={p.name:list(p.values) for p in ast.policies}
    metadata={k:_value(v)['value'] for k,v in ast.metadata}
    return {
        'spec_version':'1.0',
        'organization':{'code':ast.organization.code,'name':ast.organization.name},
        'domains':[{'code':d.code,'name':d.name or d.code,'engine':d.engine,'enabled':d.enabled,'capabilities':list(d.capabilities)} for d in ast.domains],
        'workflows':[{'code':w.code,'name':w.name or w.code,'trigger':w.trigger,'enabled':w.enabled,'steps':[{'code':s.code,'action':s.action,'requires_approval':s.requires_approval} for s in w.steps]} for w in ast.workflows],
        'policies':policies,
        'metadata':metadata,
    }

def canonical_ast(ast: ModuleAST) -> str:
    # Explicitly omit source spans: identity is semantic source structure, not whitespace/line placement.
    value={
        'module':ast.name,'version':ast.version,
        'organization':{'code':ast.organization.code,'name':ast.organization.name},
        'domains':[{'code':d.code,'engine':d.engine,'capabilities':sorted(d.capabilities),'name':d.name,'enabled':d.enabled} for d in ast.domains],
        'workflows':[{'code':w.code,'trigger':w.trigger,'steps':[{'code':s.code,'action':s.action,'requires_approval':s.requires_approval} for s in w.steps],'name':w.name,'enabled':w.enabled} for w in ast.workflows],
        'policies':{p.name:sorted(p.values) for p in ast.policies},
        'metadata':{k:_value(v) for k,v in ast.metadata},
    }
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
