from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ADMIN_ROLES, WRITE_ROLES, ensure_role, get_current_user, get_membership, require_project_access
from app.db import get_db_session
from app.models.feature_flags import EnvironmentKey, FeatureFlag, FlagEnvironmentState, Segment, TargetingRule
from app.models.identity import User
from app.models.organization import Membership
from app.models.project import Environment, Project
from app.schemas.feature_flags import (
    BatchEvaluationRequest, BatchEvaluationResponse, Condition, EnvironmentFlagStateResponse,
    EnvironmentStateUpdate, EvaluationRequest, EvaluationResult, FeatureFlagCreate,
    FeatureFlagResponse, FeatureFlagUpdate, SegmentCreate, SegmentResponse, SegmentUpdate,
    SimulationRequest, SimulationResponse, SimulationRow, TargetingRuleCreate,
    TargetingRuleResponse, TargetingRuleUpdate,
)
from app.services.audit import record_audit
from app.services.credentials import hash_sdk_key
from app.services.evaluation import FlagSnapshot, RuleSnapshot, SegmentSnapshot, evaluate_flag

router = APIRouter(tags=["feature-flags"])

def _default(flag_type: str) -> Any:
    return {"boolean": False, "string": "", "number": 0, "json": {}}[flag_type]

def _validate_value(flag_type: str, value: Any) -> None:
    if flag_type == "boolean" and not isinstance(value, bool):
        raise ValueError("Boolean flags require a boolean value")
    if flag_type == "string" and not isinstance(value, str):
        raise ValueError("String flags require a string value")
    if flag_type == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ValueError("Number flags require a numeric value")

async def _flag_access(flag_id: UUID, user: User, db: AsyncSession) -> tuple[FeatureFlag, Project, Membership]:
    flag = await db.scalar(
        select(FeatureFlag)
        .options(selectinload(FeatureFlag.environment_states).selectinload(FlagEnvironmentState.targeting_rules))
        .where(FeatureFlag.id == flag_id)
    )
    if not flag:
        raise HTTPException(404, "Feature flag not found")
    project = await db.scalar(select(Project).where(Project.id == flag.project_id))
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not project or not membership:
        raise HTTPException(404, "Feature flag not found")
    return flag, project, membership

async def _validate_segments(project_id: UUID, keys: list[str], db: AsyncSession) -> None:
    if not keys:
        return
    found = set(await db.scalars(select(Segment.key).where(Segment.project_id == project_id, Segment.key.in_(keys))))
    missing = sorted(set(keys) - found)
    if missing:
        raise HTTPException(422, f"Unknown segments: {', '.join(missing)}")

@router.get("/projects/{project_id}/flags", response_model=list[FeatureFlagResponse])
async def list_flags(project_id: UUID, include_archived: bool = False, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> list[FeatureFlag]:
    project, _ = access
    query = select(FeatureFlag).options(selectinload(FeatureFlag.environment_states).selectinload(FlagEnvironmentState.targeting_rules)).where(FeatureFlag.project_id == project.id).order_by(FeatureFlag.updated_at.desc())
    if not include_archived:
        query = query.where(FeatureFlag.is_archived.is_(False))
    return list(await db.scalars(query))

@router.post("/projects/{project_id}/flags", response_model=FeatureFlagResponse, status_code=201)
async def create_flag(project_id: UUID, payload: FeatureFlagCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> FeatureFlag:
    project = await db.scalar(select(Project).where(Project.id == project_id))
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not project or not membership:
        raise HTTPException(404, "Project not found")
    ensure_role(membership, WRITE_ROLES)
    try:
        _validate_value(payload.flag_type.value, payload.default_value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    flag = FeatureFlag(project_id=project.id, key=payload.key, name=payload.name, description=payload.description, flag_type=payload.flag_type, created_by=user.id)
    db.add(flag); await db.flush()
    for env in await db.scalars(select(Environment).where(Environment.project_id == project.id)):
        db.add(FlagEnvironmentState(flag_id=flag.id, environment_id=env.id, enabled=False, default_value=payload.default_value, version=1))
    try:
        await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="flag.created", entity_type="feature_flag", entity_id=flag.id, actor_user_id=user.id, details={"key": flag.key})
        await db.commit()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Flag key already exists") from exc
    return (await _flag_access(flag.id, user, db))[0]

@router.get("/flags/{flag_id}", response_model=FeatureFlagResponse)
async def get_flag(flag_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> FeatureFlag:
    return (await _flag_access(flag_id, user, db))[0]

@router.patch("/flags/{flag_id}", response_model=FeatureFlagResponse)
async def update_flag(flag_id: UUID, payload: FeatureFlagUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> FeatureFlag:
    flag, project, membership = await _flag_access(flag_id, user, db); ensure_role(membership, WRITE_ROLES)
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(flag, field, value)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="flag.updated", entity_type="feature_flag", entity_id=flag.id, actor_user_id=user.id, details=payload.model_dump(exclude_unset=True))
    await db.commit(); return flag

@router.delete("/flags/{flag_id}", status_code=204)
async def archive_flag(flag_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    flag, project, membership = await _flag_access(flag_id, user, db); ensure_role(membership, ADMIN_ROLES)
    flag.is_archived = True
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="flag.archived", entity_type="feature_flag", entity_id=flag.id, actor_user_id=user.id); await db.commit()

@router.patch("/flags/{flag_id}/environments/{environment_id}", response_model=EnvironmentFlagStateResponse)
async def update_environment_state(flag_id: UUID, environment_id: UUID, payload: EnvironmentStateUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> FlagEnvironmentState:
    flag, project, membership = await _flag_access(flag_id, user, db); ensure_role(membership, WRITE_ROLES)
    env = await db.scalar(select(Environment).where(Environment.id == environment_id, Environment.project_id == project.id))
    if not env: raise HTTPException(404, "Environment not found")
    try: _validate_value(flag.flag_type.value, payload.default_value)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    state = await db.scalar(select(FlagEnvironmentState).options(selectinload(FlagEnvironmentState.targeting_rules)).where(FlagEnvironmentState.flag_id == flag.id, FlagEnvironmentState.environment_id == env.id))
    if not state:
        state = FlagEnvironmentState(flag_id=flag.id, environment_id=env.id, enabled=payload.enabled, default_value=payload.default_value, version=1); db.add(state)
    else:
        state.enabled = payload.enabled; state.default_value = payload.default_value; state.version += 1
    await record_audit(db=db, organization_id=membership.organization_id, project_id=project.id, action="flag.environment_updated", entity_type="flag_environment_state", entity_id=state.id, actor_user_id=user.id, details={"enabled": state.enabled, "version": state.version})
    await db.commit(); await db.refresh(state); return state

@router.get("/flags/{flag_id}/environments/{environment_id}/rules", response_model=list[TargetingRuleResponse])
async def list_rules(flag_id: UUID, environment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> list[TargetingRule]:
    flag, project, _ = await _flag_access(flag_id, user, db)
    env = await db.scalar(select(Environment).where(Environment.id == environment_id, Environment.project_id == project.id))
    if not env: raise HTTPException(404, "Environment not found")
    state = await db.scalar(select(FlagEnvironmentState).where(FlagEnvironmentState.flag_id == flag.id, FlagEnvironmentState.environment_id == env.id))
    if not state: return []
    return list(await db.scalars(select(TargetingRule).where(TargetingRule.flag_environment_state_id == state.id).order_by(TargetingRule.priority)))

@router.post("/flags/{flag_id}/environments/{environment_id}/rules", response_model=TargetingRuleResponse, status_code=201)
async def create_rule(flag_id: UUID, environment_id: UUID, payload: TargetingRuleCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> TargetingRule:
    flag, project, membership = await _flag_access(flag_id, user, db); ensure_role(membership, WRITE_ROLES)
    env = await db.scalar(select(Environment).where(Environment.id == environment_id, Environment.project_id == project.id))
    if not env: raise HTTPException(404, "Environment not found")
    try: _validate_value(flag.flag_type.value, payload.serve_value)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    await _validate_segments(project.id, payload.segment_keys, db)
    state = await db.scalar(select(FlagEnvironmentState).where(FlagEnvironmentState.flag_id == flag.id, FlagEnvironmentState.environment_id == env.id))
    if not state:
        state = FlagEnvironmentState(flag_id=flag.id, environment_id=env.id, enabled=False, default_value=_default(flag.flag_type.value), version=1); db.add(state); await db.flush()
    priority = payload.priority
    if priority is None:
        priority = (await db.scalar(select(func.max(TargetingRule.priority)).where(TargetingRule.flag_environment_state_id == state.id)) or 0) + 1
    rule = TargetingRule(flag_environment_state_id=state.id, priority=priority, name=payload.name, conditions=[c.model_dump(mode="json") for c in payload.conditions], segment_keys=payload.segment_keys, rollout_percentage=payload.rollout_percentage, serve_value=payload.serve_value, is_enabled=payload.is_enabled)
    state.version += 1; db.add(rule)
    try:
        await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="targeting_rule.created", entity_type="targeting_rule", entity_id=rule.id, actor_user_id=user.id, details={"priority": priority}); await db.commit()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Rule priority already exists") from exc
    await db.refresh(rule); return rule

@router.patch("/rules/{rule_id}", response_model=TargetingRuleResponse)
async def update_rule(rule_id: UUID, payload: TargetingRuleUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> TargetingRule:
    rule = await db.scalar(select(TargetingRule).where(TargetingRule.id == rule_id))
    if not rule: raise HTTPException(404, "Targeting rule not found")
    state = await db.scalar(select(FlagEnvironmentState).where(FlagEnvironmentState.id == rule.flag_environment_state_id))
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.id == state.flag_id)) if state else None
    project = await db.scalar(select(Project).where(Project.id == flag.project_id)) if flag else None
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not rule or not state or not flag or not project or not membership: raise HTTPException(404, "Targeting rule not found")
    ensure_role(membership, WRITE_ROLES)
    data = payload.model_dump(exclude_unset=True)
    if data.get("serve_value") is not None:
        try: _validate_value(flag.flag_type.value, data["serve_value"])
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    if data.get("segment_keys") is not None: await _validate_segments(project.id, data["segment_keys"], db)
    if data.get("conditions") is not None: data["conditions"] = [Condition.model_validate(c).model_dump(mode="json") for c in data["conditions"]]
    for field, value in data.items(): setattr(rule, field, value)
    state.version += 1
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="targeting_rule.updated", entity_type="targeting_rule", entity_id=rule.id, actor_user_id=user.id); await db.commit(); await db.refresh(rule); return rule

@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    rule = await db.scalar(select(TargetingRule).where(TargetingRule.id == rule_id))
    if not rule: raise HTTPException(404, "Targeting rule not found")
    state = await db.scalar(select(FlagEnvironmentState).where(FlagEnvironmentState.id == rule.flag_environment_state_id))
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.id == state.flag_id)) if state else None
    project = await db.scalar(select(Project).where(Project.id == flag.project_id)) if flag else None
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not state or not project or not membership: raise HTTPException(404, "Targeting rule not found")
    ensure_role(membership, WRITE_ROLES); state.version += 1; await db.delete(rule)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="targeting_rule.deleted", entity_type="targeting_rule", entity_id=rule.id, actor_user_id=user.id); await db.commit()

@router.get("/projects/{project_id}/segments", response_model=list[SegmentResponse])
async def list_segments(project_id: UUID, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> list[Segment]:
    project, _ = access; return list(await db.scalars(select(Segment).where(Segment.project_id == project.id).order_by(Segment.name)))

@router.post("/projects/{project_id}/segments", response_model=SegmentResponse, status_code=201)
async def create_segment(project_id: UUID, payload: SegmentCreate, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> Segment:
    project, membership = access; ensure_role(membership, WRITE_ROLES)
    segment = Segment(project_id=project.id, key=payload.key, name=payload.name, description=payload.description, conditions=[c.model_dump(mode="json") for c in payload.conditions]); db.add(segment)
    try:
        await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="segment.created", entity_type="segment", entity_id=segment.id, actor_user_id=membership.user_id); await db.commit()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Segment key already exists") from exc
    await db.refresh(segment); return segment

@router.patch("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(segment_id: UUID, payload: SegmentUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Segment:
    segment = await db.scalar(select(Segment).where(Segment.id == segment_id))
    if not segment: raise HTTPException(404, "Segment not found")
    project = await db.scalar(select(Project).where(Project.id == segment.project_id)); membership = await get_membership(project.organization_id, user, db) if project else None
    if not project or not membership: raise HTTPException(404, "Segment not found")
    ensure_role(membership, WRITE_ROLES); data = payload.model_dump(exclude_unset=True)
    if data.get("conditions") is not None: data["conditions"] = [Condition.model_validate(c).model_dump(mode="json") for c in data["conditions"]]
    for field, value in data.items(): setattr(segment, field, value)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="segment.updated", entity_type="segment", entity_id=segment.id, actor_user_id=user.id); await db.commit(); await db.refresh(segment); return segment

@router.delete("/segments/{segment_id}", status_code=204)
async def delete_segment(segment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    segment = await db.scalar(select(Segment).where(Segment.id == segment_id))
    if not segment: raise HTTPException(404, "Segment not found")
    project = await db.scalar(select(Project).where(Project.id == segment.project_id)); membership = await get_membership(project.organization_id, user, db) if project else None
    if not project or not membership: raise HTTPException(404, "Segment not found")
    ensure_role(membership, ADMIN_ROLES); await db.delete(segment)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="segment.deleted", entity_type="segment", entity_id=segment.id, actor_user_id=user.id); await db.commit()

async def _environment_for_key(environment_key: str, sdk_key: str, db: AsyncSession) -> tuple[Environment, Project, EnvironmentKey]:
    key = await db.scalar(select(EnvironmentKey).options(selectinload(EnvironmentKey.environment)).where(EnvironmentKey.key_hash == hash_sdk_key(sdk_key), EnvironmentKey.revoked_at.is_(None)))
    if not key or not key.environment or key.environment.key != environment_key: raise HTTPException(401, "Invalid evaluation key")
    env = key.environment; project = await db.scalar(select(Project).where(Project.id == env.project_id))
    if not project: raise HTTPException(401, "Invalid evaluation key")
    return env, project, key

async def _snapshot(flag: FeatureFlag, env: Environment, db: AsyncSession) -> FlagSnapshot:
    state = await db.scalar(select(FlagEnvironmentState).options(selectinload(FlagEnvironmentState.targeting_rules)).where(FlagEnvironmentState.flag_id == flag.id, FlagEnvironmentState.environment_id == env.id))
    if not state:
        return FlagSnapshot(id=flag.id, key=flag.key, enabled=False, default_value=_default(flag.flag_type.value), version=0, rules=[])
    return FlagSnapshot(id=flag.id, key=flag.key, enabled=state.enabled, default_value=state.default_value, version=state.version, rules=[RuleSnapshot(id=r.id, priority=r.priority, conditions=r.conditions, segment_keys=r.segment_keys, rollout_percentage=r.rollout_percentage, serve_value=r.serve_value, is_enabled=r.is_enabled) for r in state.targeting_rules])

async def _segments(project_id: UUID, keys: set[str], db: AsyncSession) -> dict[str, SegmentSnapshot]:
    if not keys: return {}
    rows = await db.scalars(select(Segment).where(Segment.project_id == project_id, Segment.key.in_(keys)))
    return {row.key: SegmentSnapshot(row.key, row.conditions) for row in rows}

@router.post("/evaluate/batch/{environment_key}", response_model=BatchEvaluationResponse)
async def evaluate_batch(environment_key: str, payload: BatchEvaluationRequest, x_feature_key: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)) -> BatchEvaluationResponse:
    if not x_feature_key: raise HTTPException(401, "X-Feature-Key is required")
    env, project, key = await _environment_for_key(environment_key, x_feature_key, db); key.last_used_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    by_key = {f.key: f for f in await db.scalars(select(FeatureFlag).where(FeatureFlag.project_id == project.id, FeatureFlag.key.in_(payload.flag_keys), FeatureFlag.is_archived.is_(False)))}
    out = []
    for flag_key in payload.flag_keys:
        flag = by_key.get(flag_key)
        if not flag: out.append(EvaluationResult(flag_key=flag_key, value=None, reason="not_found", version=0)); continue
        snap = await _snapshot(flag, env, db); segs = await _segments(project.id, {k for r in snap.rules for k in r.segment_keys}, db); value, reason, rule_id = evaluate_flag(snap, {"user_id": payload.user_id, "attributes": payload.attributes}, segs)
        out.append(EvaluationResult(flag_key=flag.key, value=value, reason=reason, matched_rule_id=rule_id, version=snap.version))
    await db.commit()
    return BatchEvaluationResponse(environment_key=environment_key, evaluations=out)

@router.post("/evaluate/{environment_key}/{flag_key}", response_model=EvaluationResult)
async def evaluate(environment_key: str, flag_key: str, payload: EvaluationRequest, x_feature_key: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)) -> EvaluationResult:
    if not x_feature_key: raise HTTPException(401, "X-Feature-Key is required")
    env, project, key = await _environment_for_key(environment_key, x_feature_key, db); key.last_used_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.project_id == project.id, FeatureFlag.key == flag_key, FeatureFlag.is_archived.is_(False)))
    if not flag: raise HTTPException(404, "Feature flag not found")
    snap = await _snapshot(flag, env, db); segs = await _segments(project.id, {k for r in snap.rules for k in r.segment_keys}, db); value, reason, rule_id = evaluate_flag(snap, {"user_id": payload.user_id, "attributes": payload.attributes}, segs)
    await db.commit()
    return EvaluationResult(flag_key=flag.key, value=value, reason=reason, matched_rule_id=rule_id, version=snap.version)

@router.post("/projects/{project_id}/simulate", response_model=SimulationResponse)
async def simulate(project_id: UUID, payload: SimulationRequest, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> SimulationResponse:
    project, _ = access; env = await db.scalar(select(Environment).where(Environment.id == payload.environment_id, Environment.project_id == project.id))
    if not env: raise HTTPException(404, "Environment not found")
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.project_id == project.id, FeatureFlag.key == payload.flag_key, FeatureFlag.is_archived.is_(False)))
    if not flag: raise HTTPException(404, "Feature flag not found")
    snap = await _snapshot(flag, env, db); segs = await _segments(project.id, {k for r in snap.rules for k in r.segment_keys}, db)
    results = [SimulationRow(user_id=u.user_id, value=(result := evaluate_flag(snap, {"user_id": u.user_id, "attributes": u.attributes}, segs))[0], reason=result[1], matched_rule_id=result[2]) for u in payload.users]
    return SimulationResponse(flag_key=flag.key, environment_key=env.key, version=snap.version, results=results)
