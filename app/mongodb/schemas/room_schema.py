from typing import List, Optional

from pydantic import BaseModel, Field

from app.mongodb.documents.room_document import Amenity, RoomImage, RoomType


class RoomCreate(BaseModel):

    title: str = Field(..., min_length=10)

    description: str = Field(..., min_length=20)

    room_type: RoomType

    price: int = Field(..., gt=0)

    deposit: int = Field(..., ge=0)

    area: float = Field(..., gt=0)

    address: str

    ward: str

    district: str

    city: str

    max_people: int = Field(..., ge=1)

    amenities: List[Amenity] = []


class RoomUpdate(BaseModel):

    title: Optional[str] = Field(default=None, min_length=10)

    description: Optional[str] = Field(default=None, min_length=20)

    price: Optional[int] = Field(default=None, gt=0)

    deposit: Optional[int] = Field(default=None, ge=0)

    area: Optional[float] = Field(default=None, gt=0)

    max_people: Optional[int] = Field(default=None, ge=1)

    amenities: Optional[List[Amenity]] = None


class RoomResponse(BaseModel):

    id: str

    title: str

    price: int

    district: str

    city: str

    images: List[RoomImage] = []

    thumbnail_index: int = 0

    views: int

    status: str
