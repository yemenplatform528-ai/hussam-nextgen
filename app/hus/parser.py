"""Recursive-descent HUS-01 parser. It builds AST only; semantic checks are separate."""
from .ast import ModuleAST, OrganizationDecl, DomainDecl, WorkflowDecl, StepDecl, PolicyDecl, HUSValue, Span
from .lexer import Lexer, Token, HUSLexError

class HUSParseError(ValueError):
    def __init__(self, message, token):
        self.code='parse_error'; self.token=token; super().__init__(message)

def parse(source: str) -> ModuleAST:
    p=_Parser(source); return p.parse()

class _Parser:
    def __init__(self, source): self.source=source; self.t=list(Lexer(source).tokens()); self.i=0
    def cur(self): return self.t[self.i]
    def take(self, kind):
        x=self.cur()
        if x.kind!=kind: raise HUSParseError(f'expected {kind}, got {x.kind}',x)
        self.i+=1; return x
    def optional(self,kind):
        if self.cur().kind==kind: self.i+=1; return True
        return False
    def span(self,a,b): return Span(a.start,b.end,a.line,a.column)
    def scalar(self):
        x=self.cur()
        if x.kind in ('STRING','IDENT'):
            self.i+=1; return HUSValue('string' if x.kind=='STRING' else 'identifier',x.value,Span(x.start,x.end,x.line,x.column))
        if x.kind=='NUMBER':
            self.i+=1; return HUSValue('decimal' if '.' in x.value else 'integer',x.value,Span(x.start,x.end,x.line,x.column))
        if x.kind in ('true','false'):
            self.i+=1; return HUSValue('boolean',x.kind=='true',Span(x.start,x.end,x.line,x.column))
        raise HUSParseError('expected scalar',x)
    def ident(self):
        x=self.cur()
        if x.kind=='IDENT' or x.kind in {'name','engine','capabilities','enabled','trigger','action','approval'}:
            self.i+=1; return x.value
        raise HUSParseError(f'expected identifier, got {x.kind}',x)
    def string_or_ident(self):
        x=self.cur()
        if x.kind in ('STRING','IDENT'): self.i+=1; return x.value
        raise HUSParseError('expected string or identifier',x)
    def parse_list(self):
        self.take('['); vals=[]
        if self.cur().kind!=']':
            while True:
                vals.append(self.string_or_ident())
                if not self.optional(','): break
        self.take(']'); return tuple(vals)
    def parse(self):
        a=self.take('module'); name=self.ident(); self.take('version'); version=self.string_or_ident(); self.take('{')
        org=None; domains=[]; workflows=[]; policies=[]; metadata=[]
        while self.cur().kind!='}':
            k=self.cur().kind
            if k=='organization': org=self.organization()
            elif k=='domain': domains.append(self.domain())
            elif k=='workflow': workflows.append(self.workflow())
            elif k=='policy': policies.append(self.policy())
            elif k=='metadata': metadata.append(self.metadata())
            else: raise HUSParseError(f'unexpected module item: {self.cur().value}',self.cur())
            self.optional(';')
        b=self.take('}')
        if org is None: raise HUSParseError('organization declaration is required',b)
        return ModuleAST(name,version,org,tuple(domains),tuple(workflows),tuple(policies),tuple(metadata),self.span(a,b))
    def organization(self):
        a=self.take('organization'); code=None; name=None
        while self.cur().kind not in (';','domain','workflow','policy','metadata','}'):
            key=self.ident()
            self.take('='); val=self.string_or_ident()
            if key=='code': code=val
            elif key=='name': name=val
            else: raise HUSParseError(f'unknown organization field: {key}',self.cur())
        b=self.cur();
        if not code or not name: raise HUSParseError('organization requires code and name',b)
        return OrganizationDecl(code,name,Span(a.start,b.start,a.line,a.column))
    def domain(self):
        a=self.take('domain'); code=self.ident(); self.take('{'); engine=None; caps=(); name=None; enabled=True
        while self.cur().kind!='}':
            key=self.ident() if self.cur().kind=='IDENT' else self.cur().kind; self.i+=1; self.take('=')
            if key=='engine': engine=self.string_or_ident()
            elif key=='capabilities': caps=self.parse_list()
            elif key=='name': name=self.string_or_ident()
            elif key=='enabled': enabled=self.take(self.cur().kind).value=='true' if self.cur().kind in ('true','false') else (_ for _ in ()).throw(HUSParseError('enabled must be boolean',self.cur()))
            else: raise HUSParseError(f'unknown domain field: {key}',self.cur())
            self.optional(';')
        b=self.take('}')
        if engine is None: raise HUSParseError('domain requires engine',b)
        return DomainDecl(code,engine,caps,name,enabled,Span(a.start,b.end,a.line,a.column))
    def workflow(self):
        a=self.take('workflow'); code=self.ident(); self.take('{'); trigger=None; steps=[]; name=None; enabled=True
        while self.cur().kind!='}':
            if self.cur().kind=='step': steps.append(self.step())
            else:
                key=self.ident() if self.cur().kind=='IDENT' else self.cur().kind; self.i+=1; self.take('=')
                if key=='trigger': trigger=self.string_or_ident()
                elif key=='name': name=self.string_or_ident()
                elif key=='enabled':
                    x=self.cur();
                    if x.kind not in ('true','false'): raise HUSParseError('enabled must be boolean',x)
                    self.i+=1; enabled=x.kind=='true'
                else: raise HUSParseError(f'unknown workflow field: {key}',self.cur())
                self.optional(';')
        b=self.take('}')
        if not trigger or not steps: raise HUSParseError('workflow requires trigger and at least one step',b)
        return WorkflowDecl(code,trigger,tuple(steps),name,enabled,Span(a.start,b.end,a.line,a.column))
    def step(self):
        a=self.take('step'); code=self.ident(); self.take('{'); action=None; approval=False
        while self.cur().kind!='}':
            key=self.ident() if self.cur().kind=='IDENT' else self.cur().kind; self.i+=1
            if key=='approval': approval=True
            else:
                self.take('=');
                if key!='action': raise HUSParseError(f'unknown step field: {key}',self.cur())
                action=self.string_or_ident()
            self.optional(';')
        b=self.take('}')
        if not action: raise HUSParseError('step requires action',b)
        return StepDecl(code,action,approval,Span(a.start,b.end,a.line,a.column))
    def policy(self):
        a=self.take('policy'); name=self.ident(); self.take('='); values=self.parse_list(); b=self.cur(); return PolicyDecl(name,values,Span(a.start,b.start,a.line,a.column))
    def metadata(self):
        a=self.take('metadata'); key=self.ident(); self.take('='); val=self.scalar(); return key,val
