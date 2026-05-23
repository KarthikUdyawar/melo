"""SQLAlchemy models for songs and related enums."""

# app/models/song.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.core.db import Base


class SongStatus(enum.StrEnum):
    """Processing status of a song job."""

    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class Song(Base):
    """Audio processing job backed by a YouTube video."""

    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
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
        index=True,
    )
    # Metadata fields — populated by probe_metadata before download
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(256), nullable=True)
    upload_date: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (Index("ix_songs_title_trgm", "title", postgresql_using="btree"),)
