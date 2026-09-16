"""Provider-neutral model adapters. Network access is opt-in and never gets Core credentials."""
from __future__ import annotations
import json, os, urllib.request
from typing import Protocol, Iterator

class AIProvider(Protocol):
    name: str
    def generate(self, *, system: str, prompt: str, model: str|None = None) -> str: ...
    def stream(self, *, system: str, prompt: str, model: str|None = None) -> Iterator[str]: ...

class UnconfiguredProvider:
    name='unconfigured'
    def generate(self, **kwargs): raise RuntimeError('AI provider is not configured')
    def stream(self, **kwargs): raise RuntimeError('AI provider is not configured')

class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible adapter. It is deliberately isolated from domain services."""
    name='openai-compatible'
    def __init__(self, base_url: str|None=None, api_key: str|None=None, timeout: float=30.0):
        self.base_url=(base_url or os.getenv('AI_BASE_URL','')).rstrip('/')
        self.api_key=api_key or os.getenv('AI_API_KEY','')
        self.timeout=timeout
    def generate(self, *, system: str, prompt: str, model: str|None=None) -> str:
        if not self.base_url or not self.api_key: raise RuntimeError('AI provider is not configured')
        body=json.dumps({'model':model or os.getenv('AI_MODEL',''),'messages':[{'role':'system','content':system},{'role':'user','content':prompt}] ,'temperature':0}).encode()
        req=urllib.request.Request(self.base_url+'/chat/completions',data=body,headers={'Authorization':'Bearer '+self.api_key,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=self.timeout) as r:
            data=json.loads(r.read().decode())
        try: return data['choices'][0]['message']['content']
        except (KeyError,IndexError,TypeError) as e: raise RuntimeError('AI provider returned an invalid response') from e
    def stream(self, *, system: str, prompt: str, model: str|None=None):
        yield self.generate(system=system,prompt=prompt,model=model)
