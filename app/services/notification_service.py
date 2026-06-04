from datetime import datetime, timezone
from typing import Optional

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.mongodb.documents.notification_document import Notification, NotificationType
from app.mongodb.schemas.notification_schema import (
    NotificationResponse,
    NotificationListResponse,
)


class NotificationService:

    # ─────────────────────────────────────────
    # TẠO THÔNG BÁO (internal helper)
    # ─────────────────────────────────────────

    @staticmethod
    async def create(
        user_id: int,
        type: NotificationType,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> Notification:
        """Tạo một notification mới. Gọi từ các service khác."""
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
        )
        await notif.insert()
        return notif

    # ─────────────────────────────────────────
    # SHORTCUTS — gọi nhanh từ room/auth service
    # ─────────────────────────────────────────

    @staticmethod
    async def notify_room_approved(owner_id: int, room_id: str, room_title: str):
        await NotificationService.create(
            user_id=owner_id,
            type=NotificationType.room_approved,
            title="Phòng của bạn đã được duyệt 🎉",
            body=f'Phòng "{room_title}" đã được admin duyệt và hiển thị trên hệ thống.',
            data={"room_id": room_id},
        )

    @staticmethod
    async def notify_room_rejected(owner_id: int, room_id: str, room_title: str):
        await NotificationService.create(
            user_id=owner_id,
            type=NotificationType.room_rejected,
            title="Phòng của bạn bị từ chối",
            body=f'Phòng "{room_title}" không đáp ứng yêu cầu và đã bị từ chối. Vui lòng chỉnh sửa và đăng lại.',
            data={"room_id": room_id},
        )

    @staticmethod
    async def notify_room_hidden(owner_id: int, room_id: str, room_title: str):
        await NotificationService.create(
            user_id=owner_id,
            type=NotificationType.room_hidden,
            title="Phòng của bạn đã bị ẩn",
            body=f'Phòng "{room_title}" đã bị admin ẩn do vi phạm quy định. Vui lòng liên hệ hỗ trợ.',
            data={"room_id": room_id},
        )

    @staticmethod
    async def notify_account_suspended(user_id: int):
        await NotificationService.create(
            user_id=user_id,
            type=NotificationType.account_suspended,
            title="Tài khoản của bạn đã bị khóa",
            body="Tài khoản vi phạm chính sách và đã bị tạm khóa. Liên hệ hỗ trợ để biết thêm chi tiết.",
        )

    @staticmethod
    async def notify_system(user_id: int, title: str, body: str, data: Optional[dict] = None):
        await NotificationService.create(
            user_id=user_id,
            type=NotificationType.system,
            title=title,
            body=body,
            data=data,
        )

    # ─────────────────────────────────────────
    # API METHODS — dùng cho route
    # ─────────────────────────────────────────

    @staticmethod
    async def get_my_notifications(
        user_id: int,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> NotificationListResponse:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read == False)

        skip = (page - 1) * limit

        items = (
            await Notification.find(*conditions)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        total = await Notification.find(*conditions).count()

        unread_count = await Notification.find(
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).count()

        return NotificationListResponse(
            items=[NotificationResponse.from_document(n) for n in items],
            total=total,
            unread_count=unread_count,
            page=page,
            limit=limit,
        )

    @staticmethod
    async def mark_as_read(notification_id: str, user_id: int) -> NotificationResponse:
        try:
            notif = await Notification.get(PydanticObjectId(notification_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification id")

        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")

        if notif.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        notif.is_read = True
        await notif.save()
        return NotificationResponse.from_document(notif)

    @staticmethod
    async def mark_all_as_read(user_id: int) -> dict:
        """Đánh dấu tất cả notification của user là đã đọc."""
        await Notification.find(
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).update({"$set": {"is_read": True}})

        return {"message": "All notifications marked as read"}

    @staticmethod
    async def delete_notification(notification_id: str, user_id: int) -> dict:
        try:
            notif = await Notification.get(PydanticObjectId(notification_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification id")

        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")

        if notif.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        await notif.delete()
        return {"message": "Notification deleted"}

    @staticmethod
    async def get_unread_count(user_id: int) -> dict:
        count = await Notification.find(
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).count()
        return {"unread_count": count}
