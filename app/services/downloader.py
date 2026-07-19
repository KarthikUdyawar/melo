"""Audio downloader service — wraps yt-dlp for Melo."""

# app/services/downloader.py
import re
import time
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.core.log_events import LogEvent
from app.core.logging import get_logger

logger = get_logger(__name__)

_DOWNLOAD_DIR = Path("/tmp/melo")  # nosec B108

YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
_YOUTUBE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{11}$")


class SongMeta(TypedDict, total=False):
    """Metadata returned by probe_metadata() and download_audio()."""

    title: str | None
    duration: float | None
    thumbnail_url: str | None
    channel: str | None
    upload_date: str | None


class DownloadError(Exception):
    """Raised when yt-dlp fails to download or extract audio."""


def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from any supported URL format."""
    normalized_url = url if "://" in url else f"https://{url}"
    parsed = urlparse(normalized_url)
    domain = parsed.netloc.lower()

    if domain not in YOUTUBE_DOMAINS:
        raise ValueError(f"Invalid YouTube domain: {domain!r}")

    query = parse_qs(parsed.query)
    if "v" in query:
        vid = query["v"][0]
        if _YOUTUBE_ID_REGEX.match(vid):
            return vid

    path_match = re.search(
        r"/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})(?:$|[/?#&])",
        parsed.path,
    )
    if path_match:
        return path_match.group(1)

    path_segments = [s for s in parsed.path.split("/") if s]
    if path_segments:
        last_segment = path_segments[-1]
        if _YOUTUBE_ID_REGEX.match(last_segment):
            return last_segment

    raise ValueError(f"Could not extract valid YouTube video ID from: {url!r}")


def probe_metadata(url: str) -> SongMeta:
    """Extract metadata for a YouTube URL without downloading media."""
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "logger": _YtDlpLogger(),
        "socket_timeout": 15,
        "format": "140/251/250/249/139/18",
        "extractor_args": {"youtube": {"skip": ["hls", "dash"]}},
        "noplaylist": True,
    }

    logger.info(LogEvent.DOWNLOAD_STARTED, url=url, phase="probe")

    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            info = ydl.extract_info(url, download=False)
    except YtDlpDownloadError as exc:
        logger.error(LogEvent.DOWNLOAD_FAILED, url=url, error=str(exc))
        raise DownloadError(f"yt-dlp probe failed for {url!r}: {exc}") from exc
    except Exception as exc:
        logger.exception(LogEvent.DOWNLOAD_FAILED, url=url)
        raise DownloadError(f"Unexpected error probing {url!r}: {exc}") from exc

    if not info:
        raise DownloadError(f"yt-dlp returned no info for {url!r}")

    result: SongMeta = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "thumbnail_url": info.get("thumbnail"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": info.get("upload_date"),
    }

    logger.info(
        LogEvent.DOWNLOAD_DONE,
        url=url,
        phase="probe",
        title=result["title"],
        duration=result["duration"],
    )

    return result


def download_audio(url: str, song_id: str) -> tuple[Path, float | None]:
    """Download the best available audio track and convert it to MP3."""
    from app.core.metrics import download_duration_seconds
    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("download_audio") as span:
        span.set_attribute("song.id", song_id)

        _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _DOWNLOAD_DIR / f"{song_id}.mp3"

        ydl_opts: dict[str, object] = {
            "format": "140/251/250/249/139/18",
            "outtmpl": str(_DOWNLOAD_DIR / f"{song_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
            ],
            "quiet": True,
            "no_warnings": False,
            "logger": _YtDlpLogger(),
            "retries": 3,
            "socket_timeout": 30,
            "noplaylist": True,
            "extractor_args": {"youtube": {"skip": ["hls", "dash"]}},
        }

        logger.info(LogEvent.DOWNLOAD_STARTED, song_id=song_id, url=url)

        t0 = time.monotonic()
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=True)
        except YtDlpDownloadError as exc:
            logger.error(
                LogEvent.DOWNLOAD_FAILED, song_id=song_id, url=url, error=str(exc)
            )
            raise DownloadError(f"yt-dlp failed for {url!r}: {exc}") from exc
        except Exception as exc:
            logger.exception(LogEvent.DOWNLOAD_FAILED, song_id=song_id, url=url)
            raise DownloadError(f"Unexpected error downloading {url!r}: {exc}") from exc
        finally:
            download_duration_seconds.observe(time.monotonic() - t0)

        if not out_path.exists():
            logger.error(
                LogEvent.DOWNLOAD_FAILED,
                song_id=song_id,
                expected_path=str(out_path),
                reason="missing_output",
            )
            raise DownloadError(
                f"Expected output file not found after download: {out_path}",
            )

        duration: float | None = info.get("duration") if info else None
        youtube_id = info.get("id") if info else None
        if youtube_id:
            span.set_attribute("youtube.id", youtube_id)

        logger.info(
            LogEvent.DOWNLOAD_DONE,
            song_id=song_id,
            path=str(out_path),
            duration=duration,
        )
        return out_path, duration


class _YtDlpLogger:
    """Internal adapter that bridges yt-dlp's logger calls to structlog."""

    def debug(self, msg: str) -> None:
        logger.debug(msg, source="yt-dlp")

    def info(self, msg: str) -> None:
        logger.info(msg, source="yt-dlp")

    def warning(self, msg: str) -> None:
        logger.warning(msg, source="yt-dlp")

    def error(self, msg: str) -> None:
        logger.error(msg, source="yt-dlp")
