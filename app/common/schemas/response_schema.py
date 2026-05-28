from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    message: str
    data: Optional[T] = None

    @classmethod
    def success(cls, data: T = None, message: str = "Success"):
        return cls(message=message, data=data)

    @classmethod
    def error(cls, message: str):
        return cls(message=message, data=None)
