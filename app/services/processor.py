"""Audio processor using FFmpeg for trimming and speed adjustment."""

# app/services/processor.py

import subprocess  # nosec B404
import time
from pathlib import Path

from app.core.log_events import LogEvent
from app.core.logging import get_logger

logger = get_logger(__name__)

_TMP_DIR = Path("/tmp/melo")  # nosec B108


class ProcessingError(Exception):
    """Raised when FFmpeg exits with non-zero code or produces invalid output."""


def trim_audio(
    input_path: Path,
    output_path: Path,
    start: float | None,
    end: float | None,
) -> Path:
    """Trim an audio file to the given time range.

    Attempt a stream copy first, then fall back to re-encoding if the
    stream-copy operation fails.
    """
    from app.core.metrics import ffmpeg_duration_seconds
    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("ffmpeg.trim"):
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(
            LogEvent.FFMPEG_TRIM_STARTED,
            input=str(input_path),
            output=str(output_path),
            start=start,
            end=end,
        )

        seek_args = []
        if start is not None:
            seek_args += ["-ss", str(start)]
        if end is not None:
            seek_args += ["-to", str(end)]

        t0 = time.monotonic()

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

        try:
            result = subprocess.run(
                cmd_copy, capture_output=True, text=True, timeout=120
            )  # nosec B603
        except subprocess.TimeoutExpired as exc:
            output_path.unlink(missing_ok=True)
            raise ProcessingError(f"FFmpeg timed out after {exc.timeout}s") from exc

        if (
            result.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            ffmpeg_duration_seconds.labels(op="trim").observe(time.monotonic() - t0)
            logger.info(
                LogEvent.FFMPEG_TRIM_DONE,
                method="stream_copy",
                output=str(output_path),
                size_bytes=output_path.stat().st_size,
            )
            return output_path

        output_path.unlink(missing_ok=True)

        logger.warning(
            LogEvent.FFMPEG_FAILED,
            step="stream_copy",
            returncode=result.returncode,
            stderr=result.stderr[-300:] if result.stderr else "",
        )

        # ── Attempt 2: re-encode ─────────────────────────────────────────────────
        cmd_reencode = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            *seek_args,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        ]

        result = subprocess.run(
            cmd_reencode, capture_output=True, text=True
        )  # nosec B603

        if result.returncode != 0:
            output_path.unlink(missing_ok=True)
            logger.error(
                LogEvent.FFMPEG_FAILED,
                step="reencode",
                returncode=result.returncode,
                stderr=result.stderr[-500:] if result.stderr else "",
            )
            raise ProcessingError(
                f"FFmpeg re-encode failed (exit {result.returncode}): \
                {result.stderr[-300:]}"
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            raise ProcessingError(
                f"FFmpeg produced empty/missing output: {output_path}"
            )

        ffmpeg_duration_seconds.labels(op="trim").observe(time.monotonic() - t0)
        logger.info(
            LogEvent.FFMPEG_TRIM_DONE,
            method="reencode",
            output=str(output_path),
            size_bytes=output_path.stat().st_size,
        )
        return output_path


def _build_atempo_filters(speed: float) -> str:
    """Build FFmpeg atempo filter chain for the desired playback speed."""
    if speed <= 0:
        raise ValueError("speed must be > 0")

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

    return ",".join(filters)


def apply_speed(input_path: Path, output_path: Path, speed: float) -> Path:
    """Apply speed adjustment to an audio file using FFmpeg atempo filter."""
    from app.core.metrics import ffmpeg_duration_seconds
    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("ffmpeg.speed"):
        if speed == 1.0:
            import shutil

            shutil.copy2(input_path, output_path)
            return output_path

        _TMP_DIR.mkdir(parents=True, exist_ok=True)

        filter_str = _build_atempo_filters(speed)

        logger.info(
            LogEvent.FFMPEG_SPEED_STARTED,
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

        t0 = time.monotonic()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
        except OSError as exc:
            output_path.unlink(missing_ok=True)
            raise ProcessingError(f"FFmpeg launch failed: {exc}") from exc

        if result.returncode != 0:
            output_path.unlink(missing_ok=True)
            logger.error(
                LogEvent.FFMPEG_FAILED,
                step="atempo",
                returncode=result.returncode,
                stderr=result.stderr[-500:] if result.stderr else "",
            )
            raise ProcessingError(
                f"FFmpeg atempo failed (exit {result.returncode}): \
                    {result.stderr[-300:]}",
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            raise ProcessingError(
                f"FFmpeg speed produced empty/missing output: {output_path}"
            )

        ffmpeg_duration_seconds.labels(op="speed").observe(time.monotonic() - t0)
        logger.info(
            LogEvent.FFMPEG_SPEED_DONE,
            output=str(output_path),
            size_bytes=output_path.stat().st_size,
            speed=speed,
        )
        return output_path
