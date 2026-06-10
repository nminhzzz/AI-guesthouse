from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Form, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_current_admin
from app.mysql.dependencies import get_db
from app.mysql.models.user_model import User

from app.mongodb.documents.room_document import GenderType, RoomType, Amenity, RoomStatus
from app.mongodb.schemas.room_schema import (
    RoomCreate,
    RoomUpdate
)

from app.services.room_service import RoomService
from app.services.notification_service import NotificationService
from app.services.user_service import get_all_admins


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    room = await RoomService.create_room(
        room_data=room_model,
        current_user=current_user,
        images=images,
    )

    # Gửi thông báo cho tất cả admin về phòng mới chờ duyệt
    admins = get_all_admins(db)
    if admins:
        admin_ids = [a.id for a in admins]
        await NotificationService.notify_new_room_pending(
            admin_ids=admin_ids,
            room_id=str(room.id),
            room_title=room.title,
            owner_name=current_user.name,
        )

    return room


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
    room_type: RoomType | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    city: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    amenities: str | None = Query(None, description="Comma-separated list of amenities, e.g., wifi,parking"),
    gender: GenderType | None = None,
    sort_by: str = Query("created_at", regex="^(created_at|price|area|views)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    parsed_amenities = None
    if amenities:
        try:
            parsed_amenities = [Amenity(a.strip()) for a in amenities.split(",") if a.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid amenity value. Allowed: {', '.join(a.value for a in Amenity)}"
            )

    return await RoomService.search_rooms(
        room_type=room_type,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        city=city,
        district=district,
        ward=ward,
        amenities=parsed_amenities,
        gender=gender,
        sort_by=sort_by,
        sort_order=sort_order,
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
# GET MY FAVORITE ROOMS
# ======================================

@router.get("/favorites/my")
async def get_my_favorites(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    return await RoomService.get_my_favorites(
        current_user_id=current_user.id,
        page=page,
        limit=limit
    )


# ======================================
# TOGGLE FAVORITE ROOM
# ======================================

@router.post("/{room_id}/favorite")
async def toggle_favorite(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    return await RoomService.toggle_favorite(
        room_id=room_id,
        current_user_id=current_user.id
    )


# ======================================
# MARK ROOM AS RENTED
# ======================================

@router.patch("/{room_id}/rented")
async def mark_as_rented(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    return await RoomService.mark_as_rented(
        room_id=room_id,
        current_user=current_user
    )


# ======================================
# GET ROOMS BY OWNER
# ======================================

@router.get("/owner/{owner_id}")
async def get_rooms_by_owner(
    owner_id: int,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    return await RoomService.get_rooms_by_owner(
        owner_id=owner_id,
        page=page,
        limit=limit
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


# ======================================
# ADMIN — LIST ALL ROOMS (mọi status)
# ======================================

@router.get("/admin/list")
async def admin_list_rooms(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    status_filter: RoomStatus | None = Query(default=None, alias="status"),
    room_type: RoomType | None = None,
    city: str | None = None,
    district: str | None = None,
    search: str | None = None,
    sort_by: str = Query("created_at", regex="^(created_at|price|area|views)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    _: User = Depends(get_current_admin),
):
    return await RoomService.admin_list_rooms(
        page=page,
        limit=limit,
        status_filter=status_filter,
        room_type=room_type,
        city=city,
        district=district,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# ======================================
# ADMIN — APPROVE ROOM
# ======================================

@router.patch("/admin/{room_id}/approve")
async def admin_approve_room(
    room_id: str,
    _: User = Depends(get_current_admin),
):
    room = await RoomService.admin_approve_room(room_id)
    await NotificationService.notify_room_approved(
        owner_id=room.owner_id,
        room_id=room_id,
        room_title=room.title,
    )
    return room


# ======================================
# ADMIN — REJECT ROOM
# ======================================

@router.patch("/admin/{room_id}/reject")
async def admin_reject_room(
    room_id: str,
    _: User = Depends(get_current_admin),
):
    room = await RoomService.admin_reject_room(room_id)
    await NotificationService.notify_room_rejected(
        owner_id=room.owner_id,
        room_id=room_id,
        room_title=room.title,
    )
    return room


# ======================================
# ADMIN — HIDE ROOM (vi phạm)
# ======================================

@router.patch("/admin/{room_id}/hide")
async def admin_hide_room(
    room_id: str,
    _: User = Depends(get_current_admin),
):
    room = await RoomService.admin_hide_room(room_id)
    await NotificationService.notify_room_hidden(
        owner_id=room.owner_id,
        room_id=room_id,
        room_title=room.title,
    )
    return room


# ======================================
# ADMIN — RESTORE ROOM (pending lại)
# ======================================

@router.patch("/admin/{room_id}/restore")
async def admin_restore_room(
    room_id: str,
    _: User = Depends(get_current_admin),
):
    return await RoomService.admin_restore_room(room_id)


# ======================================
# ADMIN — DELETE ROOM (hard soft-delete)
# ======================================

@router.delete("/admin/{room_id}")
async def admin_delete_room(
    room_id: str,
    _: User = Depends(get_current_admin),
):
    return await RoomService.admin_delete_room(room_id)
