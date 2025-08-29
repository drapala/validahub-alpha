"""Rules domain module.

This module contains the Rules bounded context following DDD principles.
"""

from .aggregates import RuleSet
from .entities import RuleVersion
from .value_objects import (
    RuleSetId,
    RuleId,
    RuleVersionId,
    RuleDefinition,
    RuleType,
    RuleStatus,
    SemVer,
    Compatibility,
    RuleMetadata,
)
from .events import (
    RuleSetCreatedEvent,
    RuleSetPublishedEvent,
    RuleSetDeprecatedEvent,
    RuleVersionCreatedEvent,
    RuleValidatedEvent,
    RuleEvaluationEvent,
)

__all__ = [
    # Aggregates
    "RuleSet",
    # Entities
    "RuleVersion",
    # Value Objects
    "RuleSetId",
    "RuleId",
    "RuleVersionId",
    "RuleDefinition",
    "RuleType",
    "RuleStatus",
    "SemVer",
    "Compatibility",
    "RuleMetadata",
    # Events
    "RuleSetCreatedEvent",
    "RuleSetPublishedEvent",
    "RuleSetDeprecatedEvent",
    "RuleVersionCreatedEvent",
    "RuleValidatedEvent",
    "RuleEvaluationEvent",
]