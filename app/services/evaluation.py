from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable
from uuid import UUID

from app.schemas.feature_flags import ConditionOperator

@dataclass(frozen=True)
class RuleSnapshot:
    id: UUID
    priority: int
    conditions: list[dict[str, Any]]
    segment_keys: list[str]
    rollout_percentage: int | None
    serve_value: Any
    is_enabled: bool

@dataclass(frozen=True)
class SegmentSnapshot:
    key: str
    conditions: list[dict[str, Any]]

@dataclass(frozen=True)
class FlagSnapshot:
    id: UUID
    key: str
    enabled: bool
    default_value: Any
    version: int
    rules: list[RuleSnapshot]

def _get_attribute(context: dict[str, Any], attribute: str) -> tuple[bool, Any]:
    if attribute == "user_id":
        return ("user_id" in context, context.get("user_id"))
    current: Any = context.get("attributes", {})
    for part in attribute.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

def condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    present, actual = _get_attribute(context, str(condition["attribute"]))
    operator = ConditionOperator(condition["operator"])
    expected = condition.get("value")
    if operator == ConditionOperator.EXISTS:
        return present is bool(expected)
    if not present:
        return False
    if operator == ConditionOperator.EQUALS:
        return actual == expected
    if operator == ConditionOperator.NOT_EQUALS:
        return actual != expected
    if operator == ConditionOperator.IN:
        return isinstance(expected, list) and actual in expected
    if operator == ConditionOperator.NOT_IN:
        return isinstance(expected, list) and actual not in expected
    if operator == ConditionOperator.CONTAINS:
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, list):
            return expected in actual
        return False
    if operator == ConditionOperator.STARTS_WITH:
        return isinstance(actual, str) and actual.startswith(str(expected))
    if operator == ConditionOperator.ENDS_WITH:
        return isinstance(actual, str) and actual.endswith(str(expected))
    if operator in {ConditionOperator.GREATER_THAN, ConditionOperator.GREATER_THAN_OR_EQUAL, ConditionOperator.LESS_THAN, ConditionOperator.LESS_THAN_OR_EQUAL}:
        try:
            if operator == ConditionOperator.GREATER_THAN: return actual > expected
            if operator == ConditionOperator.GREATER_THAN_OR_EQUAL: return actual >= expected
            if operator == ConditionOperator.LESS_THAN: return actual < expected
            return actual <= expected
        except TypeError:
            return False
    return False

def conditions_match(conditions: Iterable[dict[str, Any]], context: dict[str, Any]) -> bool:
    return all(condition_matches(condition, context) for condition in conditions)

def segment_matches(segment: SegmentSnapshot, context: dict[str, Any]) -> bool:
    return conditions_match(segment.conditions, context)

def _bucket(flag_id: UUID, rule_id: UUID, user_id: str | None) -> int:
    seed = f"{flag_id}:{rule_id}:{user_id or 'anonymous'}".encode("utf-8")
    return int(sha256(seed).hexdigest()[:8], 16) % 100

def evaluate_flag(flag: FlagSnapshot, context: dict[str, Any], segments: dict[str, SegmentSnapshot]) -> tuple[Any, str, UUID | None]:
    if not flag.enabled:
        return flag.default_value, "disabled", None
    rollout_cursor = 0
    for rule in sorted(flag.rules, key=lambda item: (item.priority, str(item.id))):
        if not rule.is_enabled:
            continue
        if not conditions_match(rule.conditions, context):
            continue
        if any(segment_key not in segments or not segment_matches(segments[segment_key], context) for segment_key in rule.segment_keys):
            continue
        if rule.rollout_percentage is None or rule.rollout_percentage >= 100:
            return rule.serve_value, "targeting_rule", rule.id
        bucket = _bucket(flag.id, rule.id, context.get("user_id"))
        end = min(100, rollout_cursor + rule.rollout_percentage)
        if rollout_cursor <= bucket < end:
            return rule.serve_value, "rollout", rule.id
        rollout_cursor = end
        if rollout_cursor >= 100:
            break
    return flag.default_value, "default", None
