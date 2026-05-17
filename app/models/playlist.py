"""Models for playlist and playlist-song association.

This module defines the SQLAlchemy ORM models for managing playlists and the
many-to-many relationship between playlists and songs, including song ordering
within a playlist.
"""
# app/models/playlist.py

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.song import Song


class PlaylistSong(Base):
    """Association model for the many-to-many relationship between Playlist and Song.

    This is a join table with an additional `position` column to maintain the
    order of songs within each playlist.
    """
    __tablename__ = "playlist_songs"
    __table_args__ = (
        UniqueConstraint("playlist_id", "song_id", name="uq_playlist_song"),
    )

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("songs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Playlist(Base):
    """Represents a user playlist containing an ordered collection of songs.

    Attributes:
        id: Unique identifier for the playlist.
        name: Name of the playlist.
        created_at: Timestamp when the playlist was created.
        songs: List of Song objects associated with this playlist, ordered by
            the position defined in the PlaylistSong association table.
    """
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    songs: Mapped[list["Song"]] = relationship(
        "Song",
        secondary="playlist_songs",
        order_by=PlaylistSong.position,
        lazy="select",
    )
