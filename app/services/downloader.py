# app/services/downloader.py
import logging
from pathlib import Path
from typing import Any, cast

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

logger = logging.getLogger(__name__)

# Worker container writes downloads here; volume `worker_tmp` is mounted at /tmp/melo
_DOWNLOAD_DIR = Path("/tmp/melo")


class DownloadError(Exception):
    """Raised when yt-dlp fails to download or extract audio."""


def download_audio(url: str, song_id: str) -> tuple[Path, float | None]:
    """
    Download the best audio track for *url* and transcode it to mp3.

    Args:
        url:     Full YouTube URL (already validated by SongCreate).
        song_id: UUID string — used as the output filename so the worker
                 can locate the file without guessing.

    Returns:
        Tuple of (path to <song_id>.mp3, duration in seconds or None).

    Raises:
        DownloadError: on any yt-dlp failure.
    """
    _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    out_path = _DOWNLOAD_DIR / f"{song_id}.mp3"

    ydl_opts: dict[str, object] = {
        # Explicit format IDs that are always available without a JS runtime /
        # signature challenge. Tried in order; ffmpeg converts whatever lands to mp3.
        #   140 = m4a  130k AAC  (best quality, no sig needed)
        #   251 = webm 129k Opus (equivalent quality)
        #   250 = webm  70k Opus
        #   249 = webm  46k Opus
        #   139 = m4a   49k AAC  (low quality fallback)
        #    18 = mp4  360p muxed (last resort — has video, ffmpeg strips it)
        "format": "140/251/250/249/139/18",
        "outtmpl": str(_DOWNLOAD_DIR / f"{song_id}.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": False,
        "logger": _YtDlpLogger(),
        "retries": 3,
        "socket_timeout": 30,
    }

    logger.info("Starting download: song_id=%s url=%s", song_id, url)

    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            info = ydl.extract_info(url, download=True)
    except YtDlpDownloadError as exc:
        raise DownloadError(f"yt-dlp failed for {url!r}: {exc}") from exc
    except Exception as exc:
        raise DownloadError(f"Unexpected error downloading {url!r}: {exc}") from exc

    if not out_path.exists():
        raise DownloadError(
            f"Expected output file not found after download: {out_path}"
        )

    duration: float | None = None
    if info:
        duration = info.get("duration")  # seconds, float or None

    logger.info(
        "Download complete: song_id=%s path=%s duration=%s",
        song_id,
        out_path,
        duration,
    )
    return out_path, duration


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _YtDlpLogger:
    """Bridge yt-dlp's internal logger to stdlib logging."""

    def debug(self, msg: str) -> None:
        logger.debug("[yt-dlp] %s", msg)

    def info(self, msg: str) -> None:
        logger.info("[yt-dlp] %s", msg)

    def warning(self, msg: str) -> None:
        logger.warning("[yt-dlp] %s", msg)

    def error(self, msg: str) -> None:
        logger.error("[yt-dlp] %s", msg)