from uuid import UUID

from app.services.evaluation import FlagSnapshot, RuleSnapshot, SegmentSnapshot, condition_matches, evaluate_flag

def test_condition_operators_and_nested_attributes() -> None:
    context = {"user_id": "u-1", "attributes": {"plan": "pro", "flags": {"beta": True}, "age": 34}}
    assert condition_matches({"attribute": "plan", "operator": "equals", "value": "pro"}, context)
    assert condition_matches({"attribute": "flags.beta", "operator": "equals", "value": True}, context)
    assert condition_matches({"attribute": "age", "operator": "greater_than", "value": 18}, context)
    assert condition_matches({"attribute": "plan", "operator": "in", "value": ["free", "pro"]}, context)
    assert condition_matches({"attribute": "missing", "operator": "exists", "value": False}, context)
    assert not condition_matches({"attribute": "plan", "operator": "equals", "value": "free"}, context)

def test_disabled_flag_returns_default() -> None:
    flag = FlagSnapshot(UUID(int=1), "new-ui", False, False, 1, [])
    assert evaluate_flag(flag, {"user_id": "u", "attributes": {}}, {}) == (False, "disabled", None)

def test_targeting_rule_and_segment() -> None:
    rule_id = UUID(int=2)
    flag = FlagSnapshot(UUID(int=1), "new-ui", True, False, 4, [RuleSnapshot(rule_id, 1, [{"attribute": "plan", "operator": "equals", "value": "pro"}], ["beta-users"], None, True, True)])
    segment = SegmentSnapshot("beta-users", [{"attribute": "country", "operator": "equals", "value": "IN"}])
    assert evaluate_flag(flag, {"user_id": "u", "attributes": {"plan": "pro", "country": "IN"}}, {"beta-users": segment}) == (True, "targeting_rule", rule_id)
    assert evaluate_flag(flag, {"user_id": "u", "attributes": {"plan": "pro", "country": "US"}}, {"beta-users": segment}) == (False, "default", None)

def test_rollout_is_deterministic_for_a_user() -> None:
    rule_id = UUID(int=3)
    flag = FlagSnapshot(UUID(int=1), "canary", True, "stable", 7, [RuleSnapshot(rule_id, 1, [], [], 50, "canary", True)])
    context = {"user_id": "stable-user", "attributes": {}}
    first = evaluate_flag(flag, context, {})
    second = evaluate_flag(flag, context, {})
    assert first == second
    assert first[1] in {"rollout", "default"}
