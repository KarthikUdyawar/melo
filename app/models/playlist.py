"""Models for playlist and playlist-song association."""

# app/models/playlist.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.core.db import Base
from app.models.song import Song


class Playlist(Base):
    """Ordered collection of songs."""

    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    playlist_songs: Mapped[list[PlaylistSong]] = relationship(
        "PlaylistSong",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistSong.position",
    )
    songs: Mapped[list[Song]] = relationship(
        "Song",
        secondary="playlist_songs",
        order_by="PlaylistSong.position",
        viewonly=True,
    )


class PlaylistSong(Base):
    """Join table with position for ordering songs within a playlist."""

    __tablename__ = "playlist_songs"
    __table_args__ = (
        UniqueConstraint("playlist_id", "song_id", name="uq_playlist_song"),
        UniqueConstraint("playlist_id", "position", name="uq_playlist_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("songs.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    playlist: Mapped[Playlist] = relationship(
        "Playlist", back_populates="playlist_songs"
    )
    song: Mapped[Song] = relationship("Song")
