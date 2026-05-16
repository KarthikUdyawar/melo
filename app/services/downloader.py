# app/services/downloader.py
"""
Audio downloader — wraps yt-dlp for Melo.
"""

import re
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.core.logging import get_logger

logger = get_logger(__name__)

# Worker container writes downloads here; volume `worker_tmp` is mounted at /tmp/melo
_DOWNLOAD_DIR = Path("/tmp/melo")  # nosec B108

YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
_YOUTUBE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{11}$")


class SongMeta(TypedDict, total=False):
    title: str | None
    duration: float | None
    thumbnail_url: str | None
    channel: str | None
    upload_date: str | None


class DownloadError(Exception):
    """Raised when yt-dlp fails to download or extract audio."""


# ---------------------------------------------------------------------------
# YouTube ID extraction
# ---------------------------------------------------------------------------


def extract_youtube_id(url: str) -> str:
    """
    Extract YouTube video ID from any supported URL format.

    Supports: ?v=, youtu.be, /shorts/, /embed/, /live/, playlist URLs.

    Raises:
        ValueError: if no valid 11-char video ID can be extracted.
    """
    normalized_url = url if "://" in url else f"https://{url}"
    parsed = urlparse(normalized_url)
    domain = parsed.netloc.lower()

    if domain not in YOUTUBE_DOMAINS:
        raise ValueError(f"Invalid YouTube domain: {domain!r}")

    # 1. Query param (?v=...)
    query = parse_qs(parsed.query)
    if "v" in query:
        vid = query["v"][0]
        if _YOUTUBE_ID_REGEX.match(vid):
            return vid

    # 2. Path-based formats (/shorts/, /embed/, /live/, /v/)
    path_match = re.search(
        r"/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})(?:$|[/?#&])",
        parsed.path,
    )
    if path_match:
        return path_match.group(1)

    # 3. Short URL direct path segment (youtu.be/ID)
    path_segments = [s for s in parsed.path.split("/") if s]
    if path_segments:
        last_segment = path_segments[-1]
        if _YOUTUBE_ID_REGEX.match(last_segment):
            return last_segment

    raise ValueError(f"Could not extract valid YouTube video ID from: {url!r}")


# ---------------------------------------------------------------------------
# Metadata probe (no download)
# ---------------------------------------------------------------------------


def probe_metadata(url: str) -> SongMeta:
    """
    Extract metadata for *url* without downloading any media.

    Returns a dict with keys:
        title, duration, thumbnail_url, channel, upload_date

    Raises:
        DownloadError: on any yt-dlp failure.
    """
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "logger": _YtDlpLogger(),
        "socket_timeout": 15,
        # Same format selector as download — avoids JS-runtime-dependent formats
        # and suppresses the repeated "No supported JavaScript runtime" warning.
        "format": "140/251/250/249/139/18",
        # Skip format types that require JS signature extraction
        "extractor_args": {"youtube": {"skip": ["hls", "dash"]}},
        # Probe only needs top-level info, not playlist entries
        "noplaylist": True,
    }

    logger.info("probe_start", url=url)

    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            info = ydl.extract_info(url, download=False)
    except YtDlpDownloadError as exc:
        logger.error("probe_failed_yt_dlp", url=url, error=str(exc))
        raise DownloadError(f"yt-dlp probe failed for {url!r}: {exc}") from exc
    except Exception as exc:
        logger.exception("probe_failed_unexpected", url=url)
        raise DownloadError(f"Unexpected error probing {url!r}: {exc}") from exc

    if not info:
        raise DownloadError(f"yt-dlp returned no info for {url!r}")

    result: SongMeta = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "thumbnail_url": info.get("thumbnail"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": info.get("upload_date"),  # YYYYMMDD string
    }

    logger.info(
        "probe_complete",
        url=url,
        title=result["title"],
        duration=result["duration"],
        channel=result["channel"],
    )

    return result


# ---------------------------------------------------------------------------
# Audio download
# ---------------------------------------------------------------------------


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
        # Always download single video even if URL contains playlist params
        "noplaylist": True,
    }

    logger.info(
        "download_start",
        song_id=song_id,
        url=url,
        output_path=str(out_path),
    )

    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            logger.debug(
                "yt_dlp_extract_info_begin",
                song_id=song_id,
                url=url,
                options=ydl_opts,
            )

            info = ydl.extract_info(url, download=True)

            logger.debug(
                "yt_dlp_extract_info_success",
                song_id=song_id,
                title=info.get("title") if info else None,
                extractor=info.get("extractor") if info else None,
            )
    except YtDlpDownloadError as exc:
        logger.error(
            "download_failed_yt_dlp",
            song_id=song_id,
            url=url,
            error=str(exc),
        )
        raise DownloadError(f"yt-dlp failed for {url!r}: {exc}") from exc
    except Exception as exc:
        logger.exception(  # includes stack trace
            "download_failed_unexpected",
            song_id=song_id,
            url=url,
        )
        raise DownloadError(f"Unexpected error downloading {url!r}: {exc}") from exc

    if not out_path.exists():
        logger.error(
            "download_missing_output",
            song_id=song_id,
            expected_path=str(out_path),
        )
        raise DownloadError(
            f"Expected output file not found after download: {out_path}"
        )

    duration: float | None = None
    if info:
        duration = info.get("duration")

    logger.info(
        "download_complete",
        song_id=song_id,
        path=str(out_path),
        duration=duration,
    )
    return out_path, duration


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _YtDlpLogger:
    """Bridge yt-dlp's internal logger to structlog."""

    def debug(self, msg: str) -> None:
        logger.debug(msg, source="yt-dlp")

    def info(self, msg: str) -> None:
        logger.info(msg, source="yt-dlp")

    def warning(self, msg: str) -> None:
        logger.warning(msg, source="yt-dlp")

    def error(self, msg: str) -> None:
        logger.error(msg, source="yt-dlp")
