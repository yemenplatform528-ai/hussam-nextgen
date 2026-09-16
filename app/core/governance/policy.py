from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Permission:
    code: str

@dataclass(frozen=True)
class Policy:
    code: str
    required_permissions: frozenset[str]
    require_active_membership: bool = True

class PolicyDenied(PermissionError):
    pass

def require_permissions(
    granted_permissions: Iterable[str],
    required_permissions: Iterable[str],
) -> None:
    granted = set(granted_permissions)
    required = set(required_permissions)
    missing = required - granted
    if missing:
        raise PolicyDenied(
            "missing permissions: " + ", ".join(sorted(missing))
        )
