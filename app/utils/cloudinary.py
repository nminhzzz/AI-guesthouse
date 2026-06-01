import cloudinary
import cloudinary.uploader
from urllib.parse import urlparse

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


def upload_image(file_bytes: bytes, filename: str, folder: str) -> dict:
    return cloudinary.uploader.upload(
        file_bytes,
        public_id=filename,
        folder=folder,
        resource_type="image",
        overwrite=False,
    )


def extract_public_id(url: str) -> str | None:
    try:
        path = urlparse(url).path
        if "/upload/" not in path:
            return None
        transformed = path.split("/upload/", 1)[1]
        parts = transformed.split("/")
        # optional version segment like v1717211111
        if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
            parts = parts[1:]
        if not parts:
            return None
        public_with_ext = "/".join(parts)
        return public_with_ext.rsplit(".", 1)[0]
    except Exception:
        return None


def delete_image_by_url(url: str) -> None:
    public_id = extract_public_id(url)
    if not public_id:
        return
    cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)