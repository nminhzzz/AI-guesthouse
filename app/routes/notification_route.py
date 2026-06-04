from fastapi import APIRouter, Depends, Query

from app.common.schemas.response_schema import ApiResponse
from app.core.dependencies import get_current_user
from app.mysql.models.user_model import User
from app.mongodb.schemas.notification_schema import (
    NotificationListResponse,
    NotificationResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ──────────────────────────────────────────
# GET /notifications — danh sách của tôi
# ──────────────────────────────────────────

@router.get("", response_model=ApiResponse[NotificationListResponse])
async def get_my_notifications(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
):
    result = await NotificationService.get_my_notifications(
        user_id=current_user.id,
        page=page,
        limit=limit,
        unread_only=unread_only,
    )
    return ApiResponse.success(data=result, message="Notifications fetched")


# ──────────────────────────────────────────
# GET /notifications/unread-count
# ──────────────────────────────────────────

@router.get("/unread-count", response_model=ApiResponse[dict])
async def get_unread_count(
    current_user: User = Depends(get_current_user),
):
    result = await NotificationService.get_unread_count(current_user.id)
    return ApiResponse.success(data=result)


# ──────────────────────────────────────────
# PATCH /notifications/{id}/read — đọc 1 cái
# ──────────────────────────────────────────

@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationResponse])
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    result = await NotificationService.mark_as_read(notification_id, current_user.id)
    return ApiResponse.success(data=result, message="Marked as read")


# ──────────────────────────────────────────
# PATCH /notifications/read-all — đọc tất cả
# ──────────────────────────────────────────

@router.patch("/read-all", response_model=ApiResponse[dict])
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
):
    result = await NotificationService.mark_all_as_read(current_user.id)
    return ApiResponse.success(data=result, message="All marked as read")


# ──────────────────────────────────────────
# DELETE /notifications/{id}
# ──────────────────────────────────────────

@router.delete("/{notification_id}", response_model=ApiResponse[dict])
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    result = await NotificationService.delete_notification(notification_id, current_user.id)
    return ApiResponse.success(data=result, message="Notification deleted")
