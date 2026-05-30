"""Generic response envelope for API responses.

This module provides a reusable Pydantic model `Envelope` that wraps API responses
with standard metadata (status code and message) along with the actual response body.
"""
# app/schemas/envelope.py
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope[T](BaseModel):
    """Generic envelope for standardized API responses.

    This class wraps any response body with common metadata fields to ensure
    consistent API response structure across the application.

    Type Parameters:
        T: The type of the response body.

    Attributes:
        status_code: HTTP status code for the response.
        message: Human-readable message describing the response.
        body: The actual response payload (can be None).
    """
    status_code: int
    message: str
    body: T | None
