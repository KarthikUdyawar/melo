# app/schemas/song.py
import re
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"[\w\-]{11}"
)


class SongCreate(BaseModel):
    url: str
    start: float | None = None
    end: float | None = None
    speed: float = 1.0

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not YOUTUBE_REGEX.match(v.strip()):
            raise ValueError(
                "url must be a valid YouTube URL "
                "(youtube.com/watch?v=..., youtu.be/..., or shorts/)"
            )
        return v.strip()

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        if not (0.5 <= v <= 4.0):
            raise ValueError("speed must be between 0.5 and 4.0")
        return v

    @model_validator(mode="after")
    def validate_trim_range(self) -> "SongCreate":
        if self.start is not None and self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end is not None and self.end <= 0:
            raise ValueError("end must be > 0")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("start must be less than end")
        return self


class SongResponse(BaseModel):
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

    model_config = {"from_attributes": True}
