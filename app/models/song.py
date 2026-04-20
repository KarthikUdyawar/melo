# app/models/song.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SongStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[SongStatus] = mapped_column(
        Enum(SongStatus, name="songstatus"),
        nullable=False,
        default=SongStatus.pending,
        server_default=SongStatus.pending.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
