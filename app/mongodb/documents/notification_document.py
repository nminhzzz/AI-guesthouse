from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class NotificationType(str, Enum):
    # Liên quan phòng trọ
    room_approved   = "room_approved"    # Admin duyệt phòng của owner
    room_rejected   = "room_rejected"    # Admin từ chối phòng của owner
    room_hidden     = "room_hidden"      # Admin ẩn phòng vi phạm
    room_rented     = "room_rented"      # Owner đánh dấu phòng đã cho thuê

    # Liên quan tương tác
    new_message     = "new_message"      # Có tin nhắn mới
    room_favorited  = "room_favorited"   # Ai đó yêu thích phòng của owner

    # Hệ thống
    account_verified  = "account_verified"  # Xác thực email thành công
    account_suspended = "account_suspended" # Tài khoản bị khóa
    system            = "system"            # Thông báo hệ thống chung


class Notification(Document):
    # Người nhận (MySQL User.id)
    user_id: int

    # Loại thông báo
    type: NotificationType

    # Tiêu đề và nội dung
    title: str
    body: str

    # Dữ liệu liên quan (optional) — dùng để điều hướng khi click
    # Ví dụ: {"room_id": "abc123"} hoặc {"conversation_id": "xyz"}
    data: Optional[dict] = None

    # Trạng thái đọc
    is_read: bool = False

    # Thời gian
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "notifications"
        # Index để query nhanh theo user + chưa đọc
        indexes = [
            "user_id",
            [("user_id", 1), ("is_read", 1), ("created_at", -1)],
        ]
