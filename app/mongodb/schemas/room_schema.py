from pydantic import BaseModel, Field
from typing import List
from app.mongodb.documents.room_document import Amenity, RoomType, RoomImage
from typing import Optional

class RoomCreate(BaseModel):

    title: str = Field(..., min_length=10)

    description: str = Field(..., min_length=20)

    room_type: RoomType

    price: int

    deposit: int

    area: float

    address: str

    ward: str

    district: str

    city: str

    max_people: int

    amenities: List[Amenity] = []





class RoomUpdate(BaseModel):

    title: Optional[str] = None

    description: Optional[str] = None

    price: Optional[int] = None

    deposit: Optional[int] = None

    area: Optional[float] = None

    max_people: Optional[int] = None

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