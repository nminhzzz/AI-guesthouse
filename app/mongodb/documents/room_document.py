from beanie import Document
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum


class RoomImage(BaseModel):
    """Lưu thông tin ảnh với public_id để dễ xóa/cập nhật trên Cloudinary"""
    public_id: str
    url: str
    width: int
    height: int


class RoomStatus(str, Enum):
    pending = "pending"
    active = "active"
    rented = "rented"
    hidden = "hidden"
    deleted = "deleted"



class GenderType(str, Enum):
    all = "all"
    male = "male"
    female = "female"


class Amenity(str, Enum):
    wifi = "wifi"
    parking = "parking"
    air_conditioner = "air_conditioner"
    refrigerator = "refrigerator"
    washing_machine = "washing_machine"
    private_bathroom = "private_bathroom"
    security_camera = "security_camera"
    elevator = "elevator"
    balcony = "balcony"
class RoomType(str, Enum):
    room = "room"                 # phòng trọ
    apartment = "apartment"       # chung cư mini
    dormitory = "dormitory"       # ký túc xá
    house = "house"               # nhà nguyên căn


class Room(Document):

    # ===== THÔNG TIN CƠ BẢN =====

    title: str

    description: str

    room_type: RoomType

    # ===== GIÁ =====

    price: int

    deposit: int = 0

    electricity_price: int = 0

    water_price: int = 0

    internet_price: int = 0

    service_price: int = 0

    # ===== DIỆN TÍCH =====

    area: float

    # ===== ĐỊA CHỈ =====

    address: str

    ward: str

    district: str

    city: str

    latitude: Optional[float] = None

    longitude: Optional[float] = None

    # ===== SỨC CHỨA =====

    max_people: int = 1

    gender: GenderType = GenderType.all

    # ===== TIỆN ÍCH =====

    amenities: List[Amenity] = []

    # ===== HÌNH ẢNH =====

    images: List[RoomImage] = Field(default_factory=list)

    thumbnail_index: int = 0

    # ===== CHỦ PHÒNG =====

    owner_id: int

    # ===== THỐNG KÊ =====

    views: int = 0

    favorite_count: int = 0

    contact_count: int = 0

    # ===== TRẠNG THÁI =====

    status: RoomStatus = RoomStatus.pending

    # ===== THỜI GIAN =====

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "rooms"