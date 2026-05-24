"""SQLAlchemy model for user favorite songs."""

# app/models/favorite.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.core.db import Base
from app.models.song import Song


class Favorite(Base):
    """One favorite row per song (unique constraint on song_id)."""

    __tablename__ = "favorites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("songs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Soft delete — set to now() instead of hard DELETE
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    song: Mapped["Song"] = relationship("Song", backref="favorite")
