from enum import Enum

class LifecycleState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"

_TRANSITIONS = {
    LifecycleState.DRAFT: {LifecycleState.ACTIVE, LifecycleState.ARCHIVED},
    LifecycleState.ACTIVE: {LifecycleState.SUSPENDED, LifecycleState.ARCHIVED},
    LifecycleState.SUSPENDED: {LifecycleState.ACTIVE, LifecycleState.ARCHIVED},
    LifecycleState.ARCHIVED: set(),
}

class InvalidTransition(ValueError):
    pass

def transition(current: LifecycleState, target: LifecycleState) -> LifecycleState:
    if target not in _TRANSITIONS[current]:
        raise InvalidTransition(f"{current.value} -> {target.value} is not allowed")
    return target
