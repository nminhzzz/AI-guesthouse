from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from beanie import PydanticObjectId


class Favorite(Document):
    user_id: int
    room_id: PydanticObjectId
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "favorites"
