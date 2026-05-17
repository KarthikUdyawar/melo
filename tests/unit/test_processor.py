"""Unit tests for app/services/processor.py

Tests cover:
- _build_atempo_filters: correct filter chains for all speed ranges
- trim_audio: success (mocked ffmpeg), failure paths, cleanup
- apply_speed: success, failure, cleanup on error
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.processor import (
    ProcessingError,
    _build_atempo_filters,
    apply_speed,
    trim_audio,
)

# ── _build_atempo_filters ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "speed, expected",
    [
        # Identity — no filter
        (1.0, ""),
        # Within single-stage range
        (0.5, "atempo=0.500000"),
        (0.75, "atempo=0.750000"),
        (1.5, "atempo=1.500000"),
        (2.0, "atempo=2.000000"),
        # Requires chaining — slow
        (0.25, "atempo=0.5,atempo=0.500000"),
        (0.125, "atempo=0.5,atempo=0.5,atempo=0.500000"),
        # Requires chaining — fast
        (4.0, "atempo=2.0,atempo=2.000000"),
        (8.0, "atempo=2.0,atempo=2.0,atempo=2.000000"),
    ],
)
def test_build_atempo_filters(speed: float, expected: str) -> None:
    assert _build_atempo_filters(speed) == expected


def test_build_atempo_filters_all_stages_within_bounds() -> None:
    """Every stage in the chain must be in [0.5, 2.0]."""
    for speed in [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0]:
        result = _build_atempo_filters(speed)
        if not result:
            continue
        for stage in result.split(","):
            val = float(stage.split("=")[1])
            assert 0.5 <= val <= 2.0, f"stage {val} out of bounds for speed={speed}"


# ── trim_audio ────────────────────────────────────────────────────────────────


def _make_fake_mp3(path: Path, size: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfb" * (size // 2))  # fake mp3 header bytes


def _mock_run_success(output_path: Path):
    """Return a mock that simulates ffmpeg writing output_path."""

    def _side_effect(cmd, **kwargs):
        # Write fake output when ffmpeg would run
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\xff\xfb" * 512)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    return _side_effect


def _mock_run_failure():
    result = MagicMock()
    result.returncode = 1
    result.stderr = "ffmpeg: error"
    return result


@pytest.fixture
def tmp_audio(tmp_path: Path) -> Path:
    p = tmp_path / "input.mp3"
    _make_fake_mp3(p)
    return p


class TestTrimAudio:
    def test_stream_copy_success(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "out.mp3"
        with patch("subprocess.run", side_effect=_mock_run_success(out)):
            result = trim_audio(tmp_audio, out, start=0.0, end=30.0)
        assert result == out
        assert out.exists()

    def test_fallback_to_reencode_on_stream_copy_fail(
        self, tmp_path: Path, tmp_audio: Path,
    ) -> None:
        out = tmp_path / "out.mp3"
        call_count = 0

        def _side_effect(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (stream copy) fails
                r = MagicMock()
                r.returncode = 1
                r.stderr = "stream copy error"
                return r
            # Second call (reencode) succeeds
            out.write_bytes(b"\xff\xfb" * 512)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with patch("subprocess.run", side_effect=_side_effect):
            result = trim_audio(tmp_audio, out, start=None, end=30.0)

        assert call_count == 2
        assert result == out

    def test_raises_processing_error_on_both_fail(
        self, tmp_path: Path, tmp_audio: Path,
    ) -> None:
        out = tmp_path / "out.mp3"
        with (
            patch("subprocess.run", return_value=_mock_run_failure()),
            pytest.raises(ProcessingError, match="FFmpeg re-encode failed"),
        ):
            trim_audio(tmp_audio, out, start=0.0, end=30.0)

    def test_cleanup_on_failure(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "out.mp3"
        # Write a file to simulate partial output
        out.write_bytes(b"corrupt")
        with (
            patch("subprocess.run", return_value=_mock_run_failure()),
            pytest.raises(ProcessingError),
        ):
            trim_audio(tmp_audio, out, start=0.0, end=30.0)
        assert not out.exists()

    def test_no_start_no_end(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "out.mp3"
        with patch("subprocess.run", side_effect=_mock_run_success(out)):
            result = trim_audio(tmp_audio, out, start=None, end=None)
        assert result == out

    def test_start_only(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "out.mp3"
        captured_cmds: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured_cmds.append(cmd)
            out.write_bytes(b"\xff\xfb" * 512)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with patch("subprocess.run", side_effect=_capture):
            trim_audio(tmp_audio, out, start=10.0, end=None)

        assert "-ss" in captured_cmds[0]
        assert "-to" not in captured_cmds[0]

    def test_raises_on_empty_output(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "out.mp3"

        def _empty_output(cmd, **kwargs):
            # Write empty file
            out.write_bytes(b"")
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        # Both attempts return empty file
        with (
            patch("subprocess.run", side_effect=_empty_output),
            pytest.raises(ProcessingError),
        ):
            trim_audio(tmp_audio, out, start=0.0, end=30.0)


# ── apply_speed ───────────────────────────────────────────────────────────────


class TestApplySpeed:
    def test_success(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "speed.mp3"
        with patch("subprocess.run", side_effect=_mock_run_success(out)):
            result = apply_speed(tmp_audio, out, speed=2.0)
        assert result == out
        assert out.exists()

    def test_filter_chain_in_cmd(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "speed.mp3"
        captured: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured.append(cmd)
            out.write_bytes(b"\xff\xfb" * 512)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with patch("subprocess.run", side_effect=_capture):
            apply_speed(tmp_audio, out, speed=4.0)

        cmd = captured[0]
        filter_idx = cmd.index("-filter:a")
        assert "atempo=2.0,atempo=2.000000" in cmd[filter_idx + 1]

    def test_raises_on_ffmpeg_failure(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "speed.mp3"
        with (
            patch("subprocess.run", return_value=_mock_run_failure()),
            pytest.raises(ProcessingError, match="FFmpeg atempo failed"),
        ):
            apply_speed(tmp_audio, out, speed=1.5)

    def test_cleanup_on_failure(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "speed.mp3"
        out.write_bytes(b"partial")
        with (
            patch("subprocess.run", return_value=_mock_run_failure()),
            pytest.raises(ProcessingError),
        ):
            apply_speed(tmp_audio, out, speed=1.5)
        assert not out.exists()

    def test_raises_on_empty_output(self, tmp_path: Path, tmp_audio: Path) -> None:
        out = tmp_path / "speed.mp3"

        def _empty(cmd, **kwargs):
            out.write_bytes(b"")
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("subprocess.run", side_effect=_empty),
            pytest.raises(ProcessingError, match="empty"),
        ):
            apply_speed(tmp_audio, out, speed=2.0)

    @pytest.mark.parametrize("speed", [0.5, 0.75, 1.5, 2.0, 4.0])
    def test_various_speeds_succeed(
        self, tmp_path: Path, tmp_audio: Path, speed: float,
    ) -> None:
        out = tmp_path / f"speed_{speed}.mp3"
        with patch("subprocess.run", side_effect=_mock_run_success(out)):
            result = apply_speed(tmp_audio, out, speed=speed)
        assert result.exists()
