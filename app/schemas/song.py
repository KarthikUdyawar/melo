"""Pydantic schemas for song-related models and validation.

This module defines the request/response models used for YouTube song
processing, including URL validation, trim/speed settings, and preview responses.
"""
# app/schemas/song.py
import re
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/|live/)|youtu\.be/)"
    r"[\w\-]{11}",
)


class SongCreate(BaseModel):
    """Schema for creating a new song entry from a YouTube URL.

    Supports optional start/end trimming and playback speed adjustment.
    """
    url: str
    start: float | None = None
    end: float | None = None
    speed: float = 1.0

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the provided URL is a supported YouTube URL.

        Args:
            v: The URL string to validate.

        Returns:
            The stripped URL if valid.

        Raises:
            ValueError: If the URL is not a valid YouTube URL.
        """
        if not YOUTUBE_REGEX.match(v.strip()):
            raise ValueError(
                "url must be a valid YouTube URL "
                "(youtube.com/watch?v=..., youtu.be/..., or shorts/)",
            )
        return v.strip()

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        """Validate playback speed is within allowed range.

        Args:
            v: The speed multiplier.

        Returns:
            The validated speed value.

        Raises:
            ValueError: If speed is outside [0.5, 4.0].
        """
        if not (0.5 <= v <= 4.0):
            raise ValueError("speed must be between 0.5 and 4.0")
        return v

    @model_validator(mode="after")
    def validate_trim_range(self) -> "SongCreate":
        """Validate logical consistency of start/end trim values.

        Ensures start < end when both are provided and that values are non-negative.

        Returns:
            The model instance after validation.

        Raises:
            ValueError: If trim range constraints are violated.
        """
        if self.start is not None and self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end is not None and self.end <= 0:
            raise ValueError("end must be > 0")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("start must be less than end")
        return self


class PreviewRequest(BaseModel):
    """Schema for requesting metadata preview of a YouTube video."""
    url: str

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the provided URL is a supported YouTube URL.

        Args:
            v: The URL string to validate.

        Returns:
            The stripped URL if valid.

        Raises:
            ValueError: If the URL is not a valid YouTube URL.
        """
        if not YOUTUBE_REGEX.match(v.strip()):
            raise ValueError(
                "url must be a valid YouTube URL "
                "(youtube.com/watch?v=..., youtu.be/..., or shorts/)",
            )
        return v.strip()


class SongPreviewResponse(BaseModel):
    """Response model containing metadata preview for a YouTube video."""
    youtube_id: str
    title: str | None = None
    duration: float | None = None
    thumbnail_url: str | None = None
    channel: str | None = None
    upload_date: str | None = None  # YYYYMMDD string from yt-dlp


class SongResponse(BaseModel):
    """Response model for a stored song with full metadata and status."""
    id: UUID
    title: str | None = None
    youtube_id: str | None = None
    file_url: str | None = None
    duration: float | None = None
    start: float | None = None
    end: float | None = None
    speed: float = 1.0
    status: str
    # Metadata fields — populated after probe, before download completes
    thumbnail_url: str | None = None
    channel: str | None = None
    upload_date: str | None = None  # YYYYMMDD string from yt-dlp
    created_at: str
    is_favorite: bool = False

    model_config = {"from_attributes": True}
