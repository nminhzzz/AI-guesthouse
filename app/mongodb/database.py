from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

# Import all documents here so init_beanie registers them.
# When adding a new document, add it to this list.
from app.mongodb.documents.room_document import Room


DOCUMENT_MODELS = [
    Room,
    # Add new documents below as the project grows:
    # BehaviorDocument,
    # FavoriteDocument,
    # MessageDocument,
]


async def connect_mongo() -> None:
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB]
    await init_beanie(
        database=db,
        document_models=DOCUMENT_MODELS,
    )
