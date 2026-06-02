from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Form, HTTPException
from pydantic import ValidationError

from app.core.dependencies import  get_current_user
from app.mysql.models.user_model import User

from app.mongodb.schemas.room_schema import (
    RoomCreate,
    RoomUpdate
)

from app.services.room_service import RoomService


router = APIRouter(
    prefix="/rooms",
    tags=["Rooms"]
)


# ======================================
# CREATE ROOM
# ======================================

@router.post("")
async def create_room(
    room_data: str = Form(...),
    images: list[UploadFile] | None = File(default=None),
    current_user: User = Depends(get_current_user)
):
    try:
        room_model = RoomCreate.model_validate_json(room_data)
    except ValidationError as e:
        errors = "; ".join(
            f"{' -> '.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in e.errors(include_url=False)
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation Error: {errors}"
        )

    if images is None or len(images) < 3 or len(images) > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload between 3 and 6 images"
        )

    return await RoomService.create_room(
        room_data=room_model,
        current_user=current_user,
        images=images,
    )


# ======================================
# GET ALL ROOMS
# ======================================

@router.get("")
async def get_rooms(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    return await RoomService.get_rooms(
        page=page,
        limit=limit
    )


# ======================================
# SEARCH ROOMS
# ======================================

@router.get("/search/filter")
async def search_rooms(
    district: str | None = None,
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    return await RoomService.search_rooms(
        district=district,
        city=city,
        min_price=min_price,
        max_price=max_price,
        page=page,
        limit=limit
    )


# ======================================
# GET MY ROOMS
# ======================================

@router.get("/my-rooms/list")
async def get_my_rooms(
    current_user: User = Depends(get_current_user)
):
    return await RoomService.get_my_rooms(
        current_user=current_user
    )


# ======================================
# GET ROOM DETAIL
# ======================================

@router.get("/{room_id}")
async def get_room_by_id(
    room_id: str
):
    return await RoomService.get_room_by_id(
        room_id=room_id
    )


# ======================================
# UPDATE ROOM
# ======================================

@router.put("/{room_id}")
async def update_room(
    room_id: str,
    room_data: str = Form(...),
    images: list[UploadFile] | None = File(default=None),
    current_user: User = Depends(get_current_user)
):
    try:
        room_model = RoomUpdate.model_validate_json(room_data)
    except ValidationError as e:
        errors = "; ".join(
            f"{' -> '.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in e.errors(include_url=False)
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation Error: {errors}"
        )

    if images is not None and len(images) > 0:
        if len(images) < 3 or len(images) > 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload between 3 and 6 images"
            )

    return await RoomService.update_room(
        room_id=room_id,
        room_data=room_model,
        current_user=current_user,
        images=images,
    )


# ======================================
# HIDE ROOM
# ======================================

@router.patch("/{room_id}/hide")
async def hide_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    return await RoomService.hide_room(
        room_id=room_id,
        current_user=current_user
    )


# ======================================
# ACTIVATE ROOM
# ======================================

@router.patch("/{room_id}/activate")
async def activate_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    return await RoomService.activate_room(
        room_id=room_id,
        current_user=current_user
    )


# ======================================
# DELETE ROOM
# ======================================

@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    return await RoomService.delete_room(
        room_id=room_id,
        current_user=current_user
    )