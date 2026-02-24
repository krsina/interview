import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import cache as cache_module
from database import get_db
from models import FeatureFlag, FlagUserOverride
from schemas import (
    EvaluateResponse,
    FeatureFlagCreate,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagToggle,
    FeatureFlagUpdate,
    FlagUserOverrideListResponse,
    FlagUserOverrideResponse,
    FlagUserOverrideSet,
    MessageResponse,
)

router = APIRouter(prefix="/flags", tags=["Feature Flags"])

DB = Annotated[AsyncSession, Depends(get_db)]


async def _get_flag_or_404(flag_id: uuid.UUID, db: AsyncSession) -> FeatureFlag:
    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.id == flag_id)
    )
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag with id '{flag_id}' not found",
        )
    return flag


async def _get_flag_by_name_or_404(name: str, db: AsyncSession) -> FeatureFlag:
    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.name == name)
    )
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag with name '{name}' not found",
        )
    return flag


async def _get_override_or_404(
    flag_id: uuid.UUID,
    user_id: str,
    db: AsyncSession,
) -> FlagUserOverride:
    result = await db.execute(
        select(FlagUserOverride).where(
            FlagUserOverride.flag_id == flag_id,
            FlagUserOverride.user_id == user_id,
        )
    )
    override = result.scalar_one_or_none()
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No override found for flag '{flag_id}' and user '{user_id}'",
        )
    return override


# Evaluate must be declared before /{flag_id} so "evaluate" is not captured as flag_id
@router.get(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="Evaluate whether a feature is enabled for a given user",
)
async def evaluate_flag(
    db: DB,
    flag_name: str = Query(..., description="Feature flag name"),
    user_id: str = Query(..., description="User identifier"),
) -> dict:
    flag = await _get_flag_by_name_or_404(flag_name, db)
    cached = cache_module.get(flag.id, user_id)
    if cached is not None:
        return cached
    result = await db.execute(
        select(FlagUserOverride).where(
            FlagUserOverride.flag_id == flag.id,
            FlagUserOverride.user_id == user_id,
        )
    )
    override = result.scalar_one_or_none()
    if override is not None:
        enabled = override.is_enabled
        source = "override"
    else:
        enabled = flag.is_enabled
        source = "default"
    response = {
        "enabled": enabled,
        "flag_id": flag.id,
        "flag_name": flag.name,
        "user_id": user_id,
        "source": source,
    }
    cache_module.set_result(flag.id, user_id, response)
    return response


@router.post(
    "/",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a feature flag",
)
async def create_flag(payload: FeatureFlagCreate, db: DB) -> FeatureFlag:
    flag = FeatureFlag(**payload.model_dump())
    db.add(flag)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature flag with name '{payload.name}' already exists",
        )
    await db.refresh(flag)
    return flag


@router.get(
    "/",
    response_model=FeatureFlagListResponse,
    summary="List all feature flags",
)
async def list_flags(
    db: DB,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    enabled_only: bool = Query(False),
) -> dict:
    query = select(FeatureFlag)
    count_query = select(func.count()).select_from(FeatureFlag)

    if enabled_only:
        query = query.where(FeatureFlag.is_enabled.is_(True))
        count_query = count_query.where(FeatureFlag.is_enabled.is_(True))

    query = query.order_by(FeatureFlag.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    total_result = await db.execute(count_query)

    return {
        "items": list(result.scalars().all()),
        "total": total_result.scalar_one(),
    }


@router.get(
    "/{flag_id}",
    response_model=FeatureFlagResponse,
    summary="Get a feature flag by ID",
)
async def get_flag(flag_id: uuid.UUID, db: DB) -> FeatureFlag:
    return await _get_flag_or_404(flag_id, db)


@router.patch(
    "/{flag_id}",
    response_model=FeatureFlagResponse,
    summary="Partially update a feature flag",
)
async def update_flag(
    flag_id: uuid.UUID,
    payload: FeatureFlagUpdate,
    db: DB,
) -> FeatureFlag:
    flag = await _get_flag_or_404(flag_id, db)
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    for field, value in update_data.items():
        setattr(flag, field, value)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature flag with name '{update_data.get('name')}' already exists",
        )
    cache_module.invalidate_flag(flag_id)
    await db.refresh(flag)
    return flag


@router.patch(
    "/{flag_id}/toggle",
    response_model=FeatureFlagResponse,
    summary="Toggle a feature flag on or off",
)
async def toggle_flag(
    flag_id: uuid.UUID,
    payload: FeatureFlagToggle,
    db: DB,
) -> FeatureFlag:
    flag = await _get_flag_or_404(flag_id, db)
    flag.is_enabled = payload.is_enabled
    await db.flush()
    cache_module.invalidate_flag(flag_id)
    await db.refresh(flag)
    return flag


@router.delete(
    "/{flag_id}",
    response_model=MessageResponse,
    summary="Delete a feature flag",
)
async def delete_flag(flag_id: uuid.UUID, db: DB) -> dict:
    flag = await _get_flag_or_404(flag_id, db)
    await db.delete(flag)
    await db.flush()
    cache_module.invalidate_flag(flag_id)
    return {"detail": f"Feature flag '{flag.name}' deleted successfully"}


# --- User overrides ---


@router.put(
    "/{flag_id}/users/{user_id}",
    response_model=FlagUserOverrideResponse,
    summary="Set per-user override (create or replace)",
)
async def set_user_override(
    flag_id: uuid.UUID,
    user_id: str,
    payload: FlagUserOverrideSet,
    db: DB,
    response: Response,
) -> FlagUserOverride:
    await _get_flag_or_404(flag_id, db)
    result = await db.execute(
        select(FlagUserOverride).where(
            FlagUserOverride.flag_id == flag_id,
            FlagUserOverride.user_id == user_id,
        )
    )
    override = result.scalar_one_or_none()
    if override is not None:
        override.is_enabled = payload.is_enabled
        await db.flush()
        await db.refresh(override)
        cache_module.invalidate_override(flag_id, user_id)
        response.status_code = status.HTTP_200_OK
        return override
    override = FlagUserOverride(
        flag_id=flag_id,
        user_id=user_id,
        is_enabled=payload.is_enabled,
    )
    db.add(override)
    await db.flush()
    await db.refresh(override)
    cache_module.invalidate_override(flag_id, user_id)
    response.status_code = status.HTTP_201_CREATED
    return override


@router.delete(
    "/{flag_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove per-user override",
)
async def delete_user_override(
    flag_id: uuid.UUID,
    user_id: str,
    db: DB,
) -> None:
    await _get_flag_or_404(flag_id, db)
    override = await _get_override_or_404(flag_id, user_id, db)
    await db.delete(override)
    await db.flush()
    cache_module.invalidate_override(flag_id, user_id)


@router.get(
    "/{flag_id}/users",
    response_model=FlagUserOverrideListResponse,
    summary="List overrides for a flag",
)
async def list_flag_overrides(
    flag_id: uuid.UUID,
    db: DB,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    await _get_flag_or_404(flag_id, db)
    query = (
        select(FlagUserOverride)
        .where(FlagUserOverride.flag_id == flag_id)
        .order_by(FlagUserOverride.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    count_query = select(func.count()).select_from(FlagUserOverride).where(
        FlagUserOverride.flag_id == flag_id
    )
    result = await db.execute(query)
    total_result = await db.execute(count_query)
    return {
        "items": list(result.scalars().all()),
        "total": total_result.scalar_one(),
    }
