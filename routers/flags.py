import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import FeatureFlag
from schemas import (
    FeatureFlagCreate,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagToggle,
    FeatureFlagUpdate,
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
    return {"detail": f"Feature flag '{flag.name}' deleted successfully"}
