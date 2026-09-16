"""Small deterministic lexer for the HUS-01 language foundation."""
from dataclasses import dataclass
import re

KEYWORDS = {
    'module','version','organization','domain','engine','capabilities','name','enabled',
    'workflow','trigger','step','action','approval','policy','metadata','true','false',
}

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int
    end: int
    line: int
    column: int

class HUSLexError(ValueError):
    def __init__(self, message, token):
        self.code='lexical_error'; self.token=token
        super().__init__(message)

class Lexer:
    _ident=re.compile(r'[A-Za-z_][A-Za-z0-9_.-]*')
    _number=re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?')
    def __init__(self, source: str): self.source=source; self.i=0; self.line=1; self.col=1
    def _advance(self, text):
        self.i += len(text)
        if '\n' in text:
            parts=text.split('\n'); self.line += len(parts)-1; self.col=len(parts[-1])+1
        else: self.col += len(text)
    def tokens(self):
        out=[]; s=self.source
        while self.i < len(s):
            c=s[self.i]
            if c.isspace(): self._advance(c); continue
            if s.startswith('//',self.i):
                j=s.find('\n',self.i); self._advance(s[self.i:] if j<0 else s[self.i:j]); continue
            if c=='#':
                j=s.find('\n',self.i); self._advance(s[self.i:] if j<0 else s[self.i:j]); continue
            start,line,col=self.i,self.line,self.col
            if c in '{}[]=,;:': self._advance(c); out.append(Token(c,c,start,self.i,line,col)); continue
            if c=='"':
                j=self.i+1; escaped=False
                while j<len(s):
                    if escaped: escaped=False; j+=1; continue
                    if s[j]=='\\': escaped=True; j+=1; continue
                    if s[j]=='"': break
                    if s[j]=='\n':
                        tok=Token('STRING','',start,j,line,col); raise HUSLexError('unterminated string',tok)
                    j+=1
                if j>=len(s): raise HUSLexError('unterminated string',Token('STRING','',start,j,line,col))
                raw=s[self.i:j+1]
                import json
                try: value=json.loads(raw)
                except Exception: raise HUSLexError('invalid string literal',Token('STRING',raw,start,j+1,line,col))
                self._advance(raw); out.append(Token('STRING',value,start,self.i,line,col)); continue
            m=self._number.match(s,self.i)
            if m:
                v=m.group(0); self._advance(v); out.append(Token('NUMBER',v,start,self.i,line,col)); continue
            m=self._ident.match(s,self.i)
            if m:
                v=m.group(0); self._advance(v); out.append(Token(v if v in KEYWORDS else 'IDENT',v,start,self.i,line,col)); continue
            raise HUSLexError(f'unexpected character: {c}',Token('INVALID',c,start,start+1,line,col))
        out.append(Token('EOF','',self.i,self.i,self.line,self.col)); return tuple(out)
