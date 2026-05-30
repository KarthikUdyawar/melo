"""Models init."""

from app.models.favorite import Favorite
from app.models.playlist import Playlist, PlaylistSong
from app.models.song import Song, SongStatus

__all__ = ["Favorite", "Playlist", "PlaylistSong", "Song", "SongStatus"]
