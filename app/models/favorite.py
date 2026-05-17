"""SQLAlchemy model for user favorite songs.

This module defines the Favorite model which represents a user's
favorite song entry in the database.
"""
# app/models/favorite.py

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.song import Song


class Favorite(Base):
    """Represents a user's favorite song.

    Each favorite links a user to a specific song. The model enforces
    a one-to-one relationship per song (unique constraint on song_id).
    """

    __tablename__ = "favorites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("songs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one favorite row per song
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    song: Mapped["Song"] = relationship("Song", backref="favorite")
