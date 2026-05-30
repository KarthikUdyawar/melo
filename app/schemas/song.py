"""Pydantic schemas for song-related models and validation.

This module defines the request/response models used for YouTube song
processing, including URL validation, trim/speed settings, and preview responses.
"""
# app/schemas/song.py
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/|live/)|youtu\.be/)"
    r"[\w\-]{11}(?=$|[?&`#/`])",
)


def _normalize_upload_date(v: str | None) -> str | None:
    """Normalize yt-dlp YYYYMMDD date strings to ISO 8601 (YYYY-MM-DD).

    Passes through None, already-ISO dates, and any malformed values unchanged
    so callers never get a crash — only a best-effort normalization.
    """
    if v is None:
        return None
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return v  # already ISO or unrecognised — passthrough


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
    upload_date: str | None = Field(
        default=None,
        description="Upload date in ISO 8601 format (YYYY-MM-DD), \
            normalized from yt-dlp YYYYMMDD.",
    )

    @field_validator("upload_date", mode="before")
    @classmethod
    def normalize_upload_date(cls, v: str | None) -> str | None:
        """Normalize upload_date into ISO 8601 format."""
        return _normalize_upload_date(v)


class SongResponse(BaseModel):
    """Response model for a stored song with full metadata and status."""

    id: UUID = Field(description="Unique song identifier (UUID v7).")
    title: str | None = Field(default=None, description="Video title from yt-dlp.")
    youtube_id: str | None = Field(
        default=None, description="11-character YouTube video ID."
    )
    file_url: str | None = Field(
        default=None, description="MinIO object path, e.g. songs/<id>.mp3."
    )
    duration: float | None = Field(
        default=None, description="Total audio duration in seconds."
    )
    start: float | None = Field(
        default=None, description="Trim start offset in seconds."
    )
    end: float | None = Field(default=None, description="Trim end offset in seconds.")
    speed: float = Field(
        default=1.0, description="Playback speed multiplier (0.5-4.0)."
    )
    status: Literal["pending", "processing", "done", "failed"] = Field(
        description="Processing job status.",
    )
    thumbnail_url: str | None = Field(
        default=None, description="YouTube thumbnail URL."
    )
    channel: str | None = Field(default=None, description="YouTube channel name.")
    upload_date: str | None = Field(
        default=None,
        description="Upload date in ISO 8601 format (YYYY-MM-DD).",
    )
    created_at: str = Field(
        description="ISO 8601 timestamp when this record was created."
    )
    is_favorite: bool = Field(
        default=False, description="Whether this song is favorited."
    )
    stream_url: str = Field(
        description="URL to stream this song. Points to /stream when done, \
            else /songs/{id}."
    )
    effective_duration: float | None = Field(
        default=None,
        description="Playback duration after trim (end - start). \
            Falls back to full duration when trim not set.",
    )

    model_config = {"from_attributes": True}

    @field_validator("upload_date", mode="before")
    @classmethod
    def normalize_upload_date(cls, v: str | None) -> str | None:
        """Normalize upload_date into ISO 8601 format."""
        return _normalize_upload_date(v)

    @model_validator(mode="after")
    def compute_effective_duration(self) -> "SongResponse":
        """Set effective_duration = end - start when both trim points are present."""
        if self.start is not None and self.end is not None:
            self.effective_duration = self.end - self.start
        else:
            self.effective_duration = self.duration
        return self
