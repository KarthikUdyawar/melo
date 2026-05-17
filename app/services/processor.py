"""Audio processor using FFmpeg for trimming and speed adjustment.

This module provides functions to:
- Trim audio files to a specific time range [start, end]
- Change playback speed using FFmpeg's atempo filter

All operations use temporary files in `/tmp/melo`, include retry logic for robustness,
and raise ``ProcessingError`` on failure with proper cleanup.
"""
# app/services/processor.py

import subprocess  # nosec B404
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_TMP_DIR = Path("/tmp/melo") # nosec B108


class ProcessingError(Exception):
   """Raised when FFmpeg exits with non-zero code or produces invalid output."""


def trim_audio(
    input_path: Path, output_path: Path, start: float | None, end: float | None,
) -> Path:
    """Trim audio file to the given time range and save to output_path.

    Strategy
    --------
    1. First attempt: Stream copy (-c copy) — fast, no re-encoding.
    2. On failure: Retry with libmp3lame re-encode to handle codec issues.

    Args:
        input_path: Path to source MP3 file.
        output_path: Path where trimmed MP3 will be written.
        start: Start time in seconds (None = from beginning).
        end: End time in seconds (None = until end of file).

    Returns:
        The output_path on successful processing.

    Raises:
        ProcessingError: If both attempts fail or the output file is missing/empty.
    """
    _TMP_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(
        "trim_start",
        input=str(input_path),
        output=str(output_path),
        start=start,
        end=end,
    )

    # Build -ss / -to args (omit if None)
    seek_args = []
    if start is not None:
        seek_args += ["-ss", str(start)]
    if end is not None:
        seek_args += ["-to", str(end)]

    # ── Attempt 1: stream copy ───────────────────────────────────────────────
    cmd_copy = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        *seek_args,
        "-c",
        "copy",
        str(output_path),
    ]

    logger.debug("ffmpeg_stream_copy", cmd=" ".join(cmd_copy))

    result = subprocess.run(cmd_copy, capture_output=True, text=True) # nosec B603

    if (
        result.returncode == 0
        and output_path.exists()
        and output_path.stat().st_size > 0
    ):
        logger.info(
            "trim_complete",
            method="stream_copy",
            output=str(output_path),
            size_bytes=output_path.stat().st_size,
        )
        return output_path

    logger.warning(
        "stream_copy_failed",
        returncode=result.returncode,
        stderr=result.stderr[-300:] if result.stderr else "",
    )

    # Clean up potentially corrupt partial output before retry
    output_path.unlink(missing_ok=True)

    # ── Attempt 2: re-encode with libmp3lame ─────────────────────────────────
    cmd_reencode = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        *seek_args,
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",  # VBR ~190kbps — matches download quality
        str(output_path),
    ]

    logger.debug("ffmpeg_reencode", cmd=" ".join(cmd_reencode))

    result = subprocess.run(cmd_reencode, capture_output=True, text=True) # nosec B603

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        logger.error(
            "trim_failed",
            returncode=result.returncode,
            stderr=result.stderr[-500:] if result.stderr else "",
        )
        raise ProcessingError(
            "FFmpeg re-encode failed ",
            f"(exit {result.returncode}):{result.stderr[-300:]}",
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise ProcessingError(f"FFmpeg produced empty/missing output: {output_path}")

    logger.info(
        "trim_complete",
        method="reencode",
        output=str(output_path),
        size_bytes=output_path.stat().st_size,
    )
    return output_path


def _build_atempo_filters(speed: float) -> str:
    """Build FFmpeg atempo filter chain for the desired playback speed.

    FFmpeg's ``atempo`` filter only supports range 0.5–2.0 per instance.
    This function chains multiple filters to support wider speed ranges.

    Examples:
        - speed=4.0   → "atempo=2.0,atempo=2.0"
        - speed=0.25  → "atempo=0.5,atempo=0.5"
        - speed=1.5   → "atempo=1.5"
        - speed=1.0   → "" (empty string — no filter needed)

    Args:
        speed: Target speed multiplier (> 0). 1.0 = normal speed.

    Returns:
        Comma-separated atempo filter string. Empty string if speed is 1.0.
    """
    filters: list[str] = []

    if speed > 1.0:
        while speed > 2.0 + 1e-9:
            filters.append("atempo=2.0")
            speed /= 2.0
        filters.append(f"atempo={speed:.6f}")
    elif speed < 1.0:
        while speed < 0.5 - 1e-9:
            filters.append("atempo=0.5")
            speed /= 0.5
        filters.append(f"atempo={speed:.6f}")
    # speed == 1.0 → empty list, caller skips processing

    return ",".join(filters)


def apply_speed(input_path: Path, output_path: Path, speed: float) -> Path:
    """Apply speed adjustment to an audio file using FFmpeg atempo filter.

    Note:
        Callers should avoid calling this with ``speed == 1.0`` as it
        unnecessarily re-encodes the file.

    Args:
        input_path: Path to source MP3 file.
        output_path: Path where speed-adjusted MP3 will be written.
        speed: Playback speed multiplier (e.g. 2.0 = double speed).

    Returns:
        The output_path on successful processing.

    Raises:
        ProcessingError: If FFmpeg fails or produces empty/missing output.
    """
    _TMP_DIR.mkdir(parents=True, exist_ok=True)

    filter_str = _build_atempo_filters(speed)

    logger.info(
        "speed_start",
        input=str(input_path),
        output=str(output_path),
        speed=speed,
        filter=filter_str,
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-filter:a",
        filter_str,
        "-vn",
        str(output_path),
    ]

    logger.debug("ffmpeg_speed", cmd=" ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    except OSError as exc:
        output_path.unlink(missing_ok=True)
        raise ProcessingError(f"FFmpeg launch failed: {exc}") from exc

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        logger.error(
            "speed_failed",
            returncode=result.returncode,
            stderr=result.stderr[-500:] if result.stderr else "",
        )
        raise ProcessingError(
            f"FFmpeg atempo failed (exit {result.returncode}): {result.stderr[-300:]}",
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise ProcessingError(
            f"FFmpeg speed produced empty/missing output: {output_path}",
        )

    logger.info(
        "speed_complete",
        output=str(output_path),
        size_bytes=output_path.stat().st_size,
        speed=speed,
    )
    return output_path
