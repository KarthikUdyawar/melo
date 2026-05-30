"""Pydantic schemas for playlist-related request and response models."""

# app/schemas/playlist.py
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.song import SongResponse


class PlaylistCreate(BaseModel):
    """Request schema for creating a new playlist."""

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize the playlist name.

        Strips whitespace and enforces length and non-empty constraints.

        Args:
            v: The name value to validate.

        Returns:
            The cleaned name.

        Raises:
            ValueError: If name is empty or exceeds 255 characters.
        """
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return v


class PlaylistSongAdd(BaseModel):
    """Request schema for adding a song to a playlist.

    Position is managed server-side (auto-increment); this schema is kept
    for future extensibility but currently has no fields.
    """


class PlaylistResponse(BaseModel):
    """Response schema for basic playlist information."""

    id: UUID
    name: str
    created_at: str
    song_count: int = 0

    model_config = {"from_attributes": True}


class PlaylistDetailResponse(BaseModel):
    """Detailed response schema for a playlist including its songs."""

    id: UUID
    name: str
    created_at: str
    songs: list[SongResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
