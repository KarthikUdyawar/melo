# app/services/processor.py
"""
Audio processor — FFmpeg trim for Melo.
"""

import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_TMP_DIR = Path("/tmp/melo")


class ProcessingError(Exception):
    """Raised when FFmpeg exits non-zero or output file is missing."""


def trim_audio(
    input_path: Path, output_path: Path, start: float | None, end: float | None
) -> Path:
    """
    Trim *input_path* to [start, end] and write result to *output_path*.

    Strategy
    --------
    1. Try stream copy (-c copy) — fast, no re-encode, no quality loss.
    2. On non-zero exit, retry with libmp3lame re-encode — handles codec
       mismatch where stream copy silently produces corrupt output.

    Args:
        input_path:  Source mp3 (fetched from MinIO to /tmp/melo).
        output_path: Destination path for trimmed mp3.
        start:       Trim start in seconds (None = from beginning).
        end:         Trim end in seconds (None = to end of file).

    Returns:
        output_path on success.

    Raises:
        ProcessingError: if both attempts fail or output is missing.
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

    result = subprocess.run(cmd_copy, capture_output=True, text=True)

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

    result = subprocess.run(cmd_reencode, capture_output=True, text=True)

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        logger.error(
            "trim_failed",
            returncode=result.returncode,
            stderr=result.stderr[-500:] if result.stderr else "",
        )
        raise ProcessingError(
            f"FFmpeg re-encode failed (exit {result.returncode}): {result.stderr[-300:]}"
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
