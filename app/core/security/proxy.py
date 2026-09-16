from __future__ import annotations
import ipaddress
from fastapi import Request

def _trusted_networks() -> list[ipaddress._BaseNetwork]:
    raw = __import__('os').getenv('TRUSTED_PROXY_CIDRS', '')
    out=[]
    for item in raw.split(','):
        item=item.strip()
        if item:
            out.append(ipaddress.ip_network(item, strict=False))
    return out

def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else 'unknown'
    try: peer_ip=ipaddress.ip_address(peer)
    except ValueError: return peer
    if any(peer_ip in network for network in _trusted_networks()):
        forwarded = request.headers.get('X-Forwarded-For', '')
        first = forwarded.split(',')[0].strip()
        try:
            return str(ipaddress.ip_address(first))
        except ValueError: pass
    return str(peer_ip)
