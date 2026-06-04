from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import HTTPException, status, UploadFile
import cloudinary.uploader

from app.utils.cloudinary import upload_image, delete_image_by_url

from app.mongodb.documents.room_document import (
    Room,
    RoomStatus,
    RoomImage,
    GenderType,
    RoomType,
    Amenity
)
from app.mongodb.documents.favorite_document import Favorite

from app.mongodb.schemas.room_schema import (
    RoomCreate,
    RoomUpdate
)

from app.mysql.models.user_model import (
    User,
    UserRole
)


class RoomService:

    @staticmethod
    async def create_room(
        room_data: RoomCreate,
        current_user: User,
        images: list[UploadFile] | None = None,
    ) -> Room:

        if current_user.role != UserRole.owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owner can create room"
            )

        # create room first (without images) to have an id for folder
        room = Room(
            **room_data.model_dump(),
            owner_id=current_user.id,
            images=[],
            thumbnail_index=0,
        )

        await room.insert()

        # If images provided, upload to Cloudinary
        uploaded_public_ids: list[str] = []
        try:
            if images:
                if len(images) < 3 or len(images) > 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Please upload between 3 and 6 images",
                    )

                room_images: list[RoomImage] = []
                folder = f"rooms/{str(room.id)}"
                for idx, img in enumerate(images):
                    file_bytes = await img.read()
                    public_id = f"room_{str(room.id)}_{idx}"
                    res = upload_image(file_bytes, public_id, folder)
                    url = res.get("secure_url") or res.get("url")
                    width = res.get("width")
                    height = res.get("height")
                    
                    if not url:
                        raise Exception("Cloudinary upload returned no url")
                    if width is None or height is None:
                        raise Exception("Cloudinary upload returned no width/height")
                    
                    uploaded_public_ids.append(public_id)
                    room_images.append(RoomImage(
                        public_id=public_id,
                        url=url,
                        width=width,
                        height=height
                    ))

                # Update room document with image data
                room.images = room_images
                room.thumbnail_index = 0
                room.updated_at = datetime.now(timezone.utc)
                await room.save()

        except HTTPException:
            # re-raise expected HTTP errors
            raise
        except Exception as e:
            # cleanup uploaded images and remove created room
            for public_id in uploaded_public_ids:
                try:
                    cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)
                except Exception:
                    pass
            try:
                await room.delete()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload images: {str(e)}",
            )

        return room

    @staticmethod
    async def get_room_by_id(
        room_id: str
    ) -> Room:

        try:
            room = await Room.get(
                PydanticObjectId(room_id)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.status in (RoomStatus.hidden, RoomStatus.deleted):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        room.views += 1
        await room.save()

        return room

    @staticmethod
    async def get_rooms(
        page: int = 1,
        limit: int = 10
    ):

        skip = (page - 1) * limit

        rooms = (
            await Room.find(
                Room.status == RoomStatus.active
            )
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        total = await Room.find(
            Room.status == RoomStatus.active
        ).count()

        return {
            "items": rooms,
            "page": page,
            "limit": limit,
            "total": total
        }

    @staticmethod
    async def get_my_rooms(
        current_user: User
    ):

        return await Room.find(
            Room.owner_id == current_user.id,
            Room.status != RoomStatus.deleted
        ).to_list()

    @staticmethod
    async def update_room(
        room_id: str,
        room_data: RoomUpdate,
        current_user: User,
        images: list[UploadFile] | None = None,
    ) -> Room:

        try:
            room = await Room.get(
                PydanticObjectId(room_id)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not owner of this room"
            )

        # Update basic fields
        update_data = room_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(room, key, value)

        # Handle image upload if new images provided
        if images and len(images) > 0:
            uploaded_public_ids: list[str] = []
            old_images = room.images  # keep reference to delete on success

            try:
                if len(images) < 3 or len(images) > 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Please upload between 3 and 6 images",
                    )

                new_images: list[RoomImage] = []
                folder = f"rooms/{str(room.id)}"

                for idx, img in enumerate(images):
                    file_bytes = await img.read()
                    # Use timestamp-based suffix to avoid collision with old public_ids
                    public_id = f"room_{str(room.id)}_u{int(datetime.now(timezone.utc).timestamp())}_{idx}"
                    res = upload_image(file_bytes, public_id, folder)
                    url = res.get("secure_url") or res.get("url")
                    width = res.get("width")
                    height = res.get("height")

                    if not url:
                        raise Exception("Cloudinary upload returned no url")
                    if width is None or height is None:
                        raise Exception("Cloudinary upload returned no width/height")

                    uploaded_public_ids.append(public_id)
                    new_images.append(RoomImage(
                        public_id=public_id,
                        url=url,
                        width=width,
                        height=height
                    ))

                # Replace images on the document
                room.images = new_images
                room.thumbnail_index = 0

                # Delete old images from Cloudinary after successful upload
                # old_img.url contains the full Cloudinary URL — use delete_image_by_url
                for old_img in old_images:
                    try:
                        delete_image_by_url(old_img.url)
                    except Exception:
                        pass

            except HTTPException:
                # Clean up newly uploaded images before re-raising
                for pid in uploaded_public_ids:
                    try:
                        folder = f"rooms/{str(room.id)}"
                        cloudinary.uploader.destroy(
                            f"{folder}/{pid}",
                            resource_type="image",
                            invalidate=True
                        )
                    except Exception:
                        pass
                raise
            except Exception as e:
                # Clean up newly uploaded images before raising 500
                for pid in uploaded_public_ids:
                    try:
                        folder = f"rooms/{str(room.id)}"
                        cloudinary.uploader.destroy(
                            f"{folder}/{pid}",
                            resource_type="image",
                            invalidate=True
                        )
                    except Exception:
                        pass
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload images: {str(e)}",
                )

        room.updated_at = datetime.now(timezone.utc)
        await room.save()

        return room

    @staticmethod
    async def delete_room(
        room_id: str,
        current_user: User
    ):

        try:
            room = await Room.get(
                PydanticObjectId(room_id)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not owner of this room"
            )

        room.status = RoomStatus.deleted
        room.updated_at = datetime.now(timezone.utc)

        await room.save()

        return {
            "message": "Room deleted successfully"
        }

    @staticmethod
    async def search_rooms(
        room_type: RoomType | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        city: str | None = None,
        district: str | None = None,
        ward: str | None = None,
        amenities: list[Amenity] | None = None,
        gender: GenderType | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        limit: int = 10
    ):
        import re

        conditions = [Room.status == RoomStatus.active]

        if room_type:
            conditions.append(Room.room_type == room_type)

        if min_price is not None:
            conditions.append(Room.price >= min_price)
        if max_price is not None:
            conditions.append(Room.price <= max_price)

        if min_area is not None:
            conditions.append(Room.area >= min_area)
        if max_area is not None:
            conditions.append(Room.area <= max_area)

        if city:
            conditions.append(
                {"city": {"$regex": re.escape(city), "$options": "i"}}
            )

        if district:
            conditions.append(
                {"district": {"$regex": re.escape(district), "$options": "i"}}
            )

        if ward:
            conditions.append(
                {"ward": {"$regex": re.escape(ward), "$options": "i"}}
            )

        if gender and gender != GenderType.all:
            conditions.append({"gender": {"$in": [gender, GenderType.all]}})

        if amenities:
            conditions.append({"amenities": {"$all": [a.value for a in amenities]}})

        skip = (page - 1) * limit
        sort_field = f"-{sort_by}" if sort_order == "desc" else f"+{sort_by}"

        rooms = (
            await Room.find(*conditions)
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        total = await Room.find(*conditions).count()

        return {
            "items": rooms,
            "page": page,
            "limit": limit,
            "total": total
        }

    @staticmethod
    async def hide_room(
        room_id: str,
        current_user: User
    ):

        try:
            room = await Room.get(
                PydanticObjectId(room_id)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not owner of this room"
            )

        room.status = RoomStatus.hidden
        room.updated_at = datetime.now(timezone.utc)

        await room.save()

        return room

    @staticmethod
    async def activate_room(
        room_id: str,
        current_user: User
    ):

        try:
            room = await Room.get(
                PydanticObjectId(room_id)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not owner of this room"
            )

        if room.status == RoomStatus.deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot activate a deleted room"
            )

        room.status = RoomStatus.active
        room.updated_at = datetime.now(timezone.utc)

        await room.save()

        return room

    @staticmethod
    async def toggle_favorite(room_id: str, current_user_id: int) -> dict:
        try:
            r_id = PydanticObjectId(room_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        room = await Room.get(r_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        fav = await Favorite.find_one(
            Favorite.user_id == current_user_id,
            Favorite.room_id == r_id
        )

        if fav:
            await fav.delete()
            room.favorite_count = max(0, room.favorite_count - 1)
            await room.save()
            return {
                "is_favorite": False,
                "favorite_count": room.favorite_count,
                "message": "Removed from favorites"
            }
        else:
            fav = Favorite(user_id=current_user_id, room_id=r_id)
            await fav.insert()
            room.favorite_count += 1
            await room.save()
            return {
                "is_favorite": True,
                "favorite_count": room.favorite_count,
                "message": "Added to favorites"
            }

    @staticmethod
    async def get_my_favorites(current_user_id: int, page: int = 1, limit: int = 10):
        skip = (page - 1) * limit

        favs = await Favorite.find(Favorite.user_id == current_user_id).to_list()
        room_ids = [f.room_id for f in favs]

        if not room_ids:
            return {
                "items": [],
                "page": page,
                "limit": limit,
                "total": 0
            }

        conditions = [
            {"_id": {"$in": room_ids}},
            Room.status != RoomStatus.deleted
        ]

        rooms = await Room.find(*conditions).skip(skip).limit(limit).to_list()
        total = await Room.find(*conditions).count()

        return {
            "items": rooms,
            "page": page,
            "limit": limit,
            "total": total
        }

    @staticmethod
    async def mark_as_rented(room_id: str, current_user: User) -> Room:
        try:
            r_id = PydanticObjectId(room_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room id"
            )

        room = await Room.get(r_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not owner of this room"
            )

        room.status = RoomStatus.rented
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return room

    @staticmethod
    async def get_rooms_by_owner(owner_id: int, page: int = 1, limit: int = 10):
        skip = (page - 1) * limit

        conditions = [
            Room.owner_id == owner_id,
            {"status": {"$in": [RoomStatus.active, RoomStatus.rented]}}
        ]

        rooms = (
            await Room.find(*conditions)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        total = await Room.find(*conditions).count()

        return {
            "items": rooms,
            "page": page,
            "limit": limit,
            "total": total
        }

    # ==========================================
    # ADMIN METHODS
    # ==========================================

    @staticmethod
    async def admin_list_rooms(
        page: int = 1,
        limit: int = 10,
        status_filter=None,
        room_type=None,
        city: str | None = None,
        district: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        import re as _re

        conditions = []

        if status_filter is not None:
            conditions.append(Room.status == status_filter)
        else:
            # Hiển thị tất cả trừ đã xóa
            conditions.append(Room.status != RoomStatus.deleted)

        if room_type is not None:
            conditions.append(Room.room_type == room_type)

        if city:
            conditions.append({"city": {"$regex": _re.escape(city), "$options": "i"}})

        if district:
            conditions.append({"district": {"$regex": _re.escape(district), "$options": "i"}})

        if search:
            conditions.append({
                "$or": [
                    {"title": {"$regex": _re.escape(search), "$options": "i"}},
                    {"address": {"$regex": _re.escape(search), "$options": "i"}},
                ]
            })

        skip = (page - 1) * limit
        sort_field = f"-{sort_by}" if sort_order == "desc" else f"+{sort_by}"

        query = Room.find(*conditions) if conditions else Room.find()
        rooms = await query.sort(sort_field).skip(skip).limit(limit).to_list()

        count_query = Room.find(*conditions) if conditions else Room.find()
        total = await count_query.count()

        return {
            "items": rooms,
            "page": page,
            "limit": limit,
            "total": total,
        }

    @staticmethod
    async def admin_approve_room(room_id: str) -> Room:
        try:
            room = await Room.get(PydanticObjectId(room_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid room id")

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.status == RoomStatus.deleted:
            raise HTTPException(status_code=400, detail="Cannot approve a deleted room")

        room.status = RoomStatus.active
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return room

    @staticmethod
    async def admin_reject_room(room_id: str) -> Room:
        try:
            room = await Room.get(PydanticObjectId(room_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid room id")

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.status == RoomStatus.deleted:
            raise HTTPException(status_code=400, detail="Cannot reject a deleted room")

        room.status = RoomStatus.hidden
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return room

    @staticmethod
    async def admin_hide_room(room_id: str) -> Room:
        try:
            room = await Room.get(PydanticObjectId(room_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid room id")

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.status == RoomStatus.deleted:
            raise HTTPException(status_code=400, detail="Cannot hide a deleted room")

        room.status = RoomStatus.hidden
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return room

    @staticmethod
    async def admin_restore_room(room_id: str) -> Room:
        """Khôi phục phòng bị ẩn/reject về pending để duyệt lại."""
        try:
            room = await Room.get(PydanticObjectId(room_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid room id")

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.status == RoomStatus.deleted:
            raise HTTPException(status_code=400, detail="Cannot restore a deleted room")

        room.status = RoomStatus.pending
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return room

    @staticmethod
    async def admin_delete_room(room_id: str) -> dict:
        try:
            room = await Room.get(PydanticObjectId(room_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid room id")

        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        room.status = RoomStatus.deleted
        room.updated_at = datetime.now(timezone.utc)
        await room.save()
        return {"message": "Room deleted successfully"}
