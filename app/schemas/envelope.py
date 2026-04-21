from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope[T](BaseModel):
    status_code: int
    message: str
    body: T | None
