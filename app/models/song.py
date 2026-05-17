"""SQLAlchemy models for songs and related enums.

This module defines the database models and enums used for managing
YouTube audio processing jobs (download, trimming, speed adjustment, etc.).
"""
# app/models/song.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SongStatus(enum.StrEnum):
    """Enum representing the processing status of a song."""
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class Song(Base):
    """SQLAlchemy model representing a song / audio processing job.

    Each row corresponds to a YouTube video that needs to be downloaded,
    optionally trimmed and speed-adjusted, then stored.
    """

    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,  # NOTE: removed unique=True —
        # dedup now allows multiple rows per youtube_id
    )
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    start: Mapped[float | None] = mapped_column(Float, nullable=True)
    end: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[SongStatus] = mapped_column(
        Enum(SongStatus, name="songstatus"),
        nullable=False,
        default=SongStatus.pending,
        server_default=SongStatus.pending.value,
    )
    # Metadata fields — populated by probe_metadata before download
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(256), nullable=True)
    upload_date: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
