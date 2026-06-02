from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from uuid import uuid4

from app.common.schemas.pagination_schema import PaginatedData
from app.common.schemas.response_schema import ApiResponse
from app.core.dependencies import get_current_admin, get_current_user
from app.mysql.dependencies import get_db
from app.mysql.models.user_model import User, UserRole
from app.mysql.schemas.user_schema import (
    SortOrder,
    UserAdminCreate,
    UserAdminUpdate,
    UserResponse,
    UserSortField,
)
from app.services.session_service import revoke_all_user_sessions
from app.services.user_service import (
    build_paginated_result,
    create_user_admin,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user_avatar,
    update_user_admin,
)
from app.utils.rate_limiter import check_user_write_rate_limit

router = APIRouter(prefix="/users", tags=["Users"])
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _upload_avatar_to_cloudinary(avatar: UploadFile, user_prefix: str) -> str:
    if avatar.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, and WEBP files are allowed",
        )

    file_bytes = await avatar.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    try:
        from app.utils.cloudinary import upload_image

        upload_result = upload_image(
            file_bytes=file_bytes,
            filename=f"{user_prefix}_{uuid4().hex}",
            folder="ai_guesthouse/users/avatars",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Avatar upload failed: {str(exc)}") from exc

    avatar_url = upload_result.get("secure_url")
    if not avatar_url:
        raise HTTPException(status_code=500, detail="Cloudinary did not return image URL")
    return avatar_url


@router.get("", response_model=ApiResponse[PaginatedData[UserResponse]])
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Tìm theo name, email, phone"),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    sort_by: UserSortField = Query("created_at"),
    sort_order: SortOrder = Query("desc"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    users, total = list_users(
        db,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        is_active=is_active,
        is_verified=is_verified,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    paginated = build_paginated_result(users, total, page, page_size)
    return ApiResponse.success(
        data=PaginatedData[UserResponse](
            items=[UserResponse.model_validate(u) for u in paginated["items"]],
            total=paginated["total"],
            page=paginated["page"],
            page_size=paginated["page_size"],
            total_pages=paginated["total_pages"],
        ),
        message="Users fetched successfully",
    )


@router.post("/me/avatar", response_model=ApiResponse[UserResponse])
async def upload_my_avatar(
    avatar: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client_ip = request.client.host if request and request.client else "unknown"
    check_user_write_rate_limit(client_ip)

    old_avatar_url = current_user.avatar_url
    avatar_url = await _upload_avatar_to_cloudinary(
        avatar=avatar,
        user_prefix=f"user_{current_user.id}",
    )

    if old_avatar_url and old_avatar_url != avatar_url:
        try:
            from app.utils.cloudinary import delete_image_by_url

            delete_image_by_url(old_avatar_url)
        except Exception:
            # Don't block avatar update when cleanup fails.
            pass

    user = update_user_avatar(db, current_user, avatar_url)
    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="Avatar uploaded successfully",
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse.success(
        data=UserResponse.model_validate(current_user),
        message="Current user fetched successfully",
    )


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="User fetched successfully",
    )


@router.post("", response_model=ApiResponse[UserResponse], status_code=201)
async def create_user(
    payload: UserAdminCreate = Depends(UserAdminCreate.as_form),
    avatar: UploadFile | None = File(None),
    request: Request = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    client_ip = request.client.host if request and request.client else "unknown"
    check_user_write_rate_limit(client_ip)

    existing = get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    if avatar is not None:
        payload.avatar_url = await _upload_avatar_to_cloudinary(
            avatar=avatar,
            user_prefix=f"user_new_{payload.email}",
        )

    user = create_user_admin(db, payload)
    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="User created successfully",
    )


@router.put("/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(
    user_id: int,
    payload: UserAdminUpdate = Depends(UserAdminUpdate.as_form),
    avatar: UploadFile | None = File(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    client_ip = request.client.host if request and request.client else "unknown"
    check_user_write_rate_limit(client_ip)

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email:
        existing = get_user_by_email(db, payload.email)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Email already exists")

    if user.id == current_admin.id:
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        if payload.role is not None and payload.role != UserRole.admin:
            raise HTTPException(status_code=400, detail="Cannot change your own admin role")

    if avatar is not None:
        old_avatar_url = user.avatar_url
        payload.avatar_url = await _upload_avatar_to_cloudinary(
            avatar=avatar,
            user_prefix=f"user_{user.id}",
        )
        if old_avatar_url and old_avatar_url != payload.avatar_url:
            try:
                from app.utils.cloudinary import delete_image_by_url

                delete_image_by_url(old_avatar_url)
            except Exception:
                pass

    was_active = user.is_active
    user = update_user_admin(db, user, payload)

    if was_active and user.is_active is False:
        revoke_all_user_sessions(str(user.id))

    if payload.role is not None or payload.password is not None:
        revoke_all_user_sessions(str(user.id))

    return ApiResponse.success(
        data=UserResponse.model_validate(user),
        message="User updated successfully",
    )


@router.delete("/{user_id}", response_model=ApiResponse[None])
def remove_user(
    user_id: int,
    hard_delete: bool = Query(False, description="Xóa vĩnh viễn khỏi database"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    client_ip = request.client.host if request and request.client else "unknown"
    check_user_write_rate_limit(client_ip)

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    delete_user(db, user, hard_delete=hard_delete)
    revoke_all_user_sessions(str(user.id))

    message = "User deleted permanently" if hard_delete else "User deactivated successfully"
    return ApiResponse.success(message=message)
