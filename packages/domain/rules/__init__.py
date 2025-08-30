"""Rules domain module.

This module contains the Rules bounded context following DDD principles.
"""

from .aggregates import RuleSet
from .entities import RuleVersion
from .events import (
    RuleEvaluationEvent,
    RuleSetCreatedEvent,
    RuleSetDeprecatedEvent,
    RuleSetPublishedEvent,
    RuleValidatedEvent,
    RuleVersionCreatedEvent,
)
from .value_objects import (
    Compatibility,
    RuleDefinition,
    RuleId,
    RuleMetadata,
    RuleSetId,
    RuleStatus,
    RuleType,
    RuleVersionId,
    SemVer,
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