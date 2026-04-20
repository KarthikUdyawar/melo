import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.song import Song


class PlaylistSong(Base):
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

    songs: Mapped[list["Song"]] = relationship(  # noqa: F821
        "Song",
        secondary="playlist_songs",
        backref="playlists",
        order_by=PlaylistSong.position,
    )
