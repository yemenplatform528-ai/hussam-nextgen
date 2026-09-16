"""HUS-01 closed type vocabulary. Types are descriptive and never executable."""
from enum import Enum

class HUSType(str, Enum):
    STRING='String'; BOOLEAN='Boolean'; INTEGER='Integer'; DECIMAL='Decimal'
    MONEY='Money'; CURRENCY='Currency'; DATE='Date'; DATETIME='DateTime'; DURATION='Duration'
    UUID='UUID'; IDENTIFIER='Identifier'; ENUM='Enum'; LIST='List'; MAP='Map'; OPTIONAL='Optional'
    ENTITY_REF='EntityRef'; SECRET_REF='SecretRef'; APPROVAL_REF='ApprovalRef'; CAPABILITY_REF='CapabilityRef'

_LITERAL_TYPES = {'string': HUSType.STRING, 'boolean': HUSType.BOOLEAN, 'integer': HUSType.INTEGER, 'decimal': HUSType.DECIMAL}

def literal_type(kind: str) -> HUSType:
    return _LITERAL_TYPES[kind]
