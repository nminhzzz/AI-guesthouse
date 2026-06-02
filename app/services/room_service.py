from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import HTTPException, status, UploadFile
import cloudinary.uploader

from app.utils.cloudinary import upload_image, delete_image_by_url

from app.mongodb.documents.room_document import (
    Room,
    RoomStatus,
    RoomImage
)

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
        district: str | None = None,
        city: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        page: int = 1,
        limit: int = 10
    ):
        import re

        conditions = [Room.status == RoomStatus.active]

        if district:
            conditions.append(
                {"district": {"$regex": re.escape(district), "$options": "i"}}
            )

        if city:
            conditions.append(
                {"city": {"$regex": re.escape(city), "$options": "i"}}
            )

        if min_price is not None and max_price is not None:
            conditions.append(Room.price >= min_price)
            conditions.append(Room.price <= max_price)
        elif min_price is not None:
            conditions.append(Room.price >= min_price)
        elif max_price is not None:
            conditions.append(Room.price <= max_price)

        skip = (page - 1) * limit

        rooms = (
            await Room.find(*conditions)
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
