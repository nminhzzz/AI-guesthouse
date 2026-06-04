from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.mongodb.documents.notification_document import NotificationType


class NotificationResponse(BaseModel):
    id: str
    user_id: int
    type: NotificationType
    title: str
    body: str
    data: Optional[dict] = None
    is_read: bool
    created_at: datetime

    @classmethod
    def from_document(cls, doc) -> "NotificationResponse":
        return cls(
            id=str(doc.id),
            user_id=doc.user_id,
            type=doc.type,
            title=doc.title,
            body=doc.body,
            data=doc.data,
            is_read=doc.is_read,
            created_at=doc.created_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    limit: int
