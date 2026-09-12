import { render, screen, fireEvent } from "@testing-library/react";
import { SongCard } from "./SongCard";
import type { Song } from "@/lib/types";

const baseSong: Song = {
  id: "1",
  title: "Test Song",
  youtube_id: "abc",
  file_url: "songs/1.mp3",
  duration: 213,
  start: null,
  end: null,
  speed: 1.0,
  status: "done",
  thumbnail_url: null,
  channel: "Chan",
  upload_date: "2024-01-01",
  created_at: "2024-01-01T00:00:00",
  is_favorite: false,
  stream_url: "/songs/1/stream",
  effective_duration: 213,
};

const noop = () => {};

test("done song is clickable, calls onPlay", () => {
  const onPlay = jest.fn();
  render(
    <SongCard song={baseSong} isActive={false} playlistNames={[]}
      onPlay={onPlay} onToggleFavorite={noop} onAddToPlaylist={noop}
      onNewPlaylist={noop} onDelete={noop} onRetry={noop} />
  );
  fireEvent.click(screen.getByRole("listitem"));
  expect(onPlay).toHaveBeenCalledTimes(1);
});

test("pending song click does not call onPlay", () => {
  const onPlay = jest.fn();
  render(
    <SongCard song={{ ...baseSong, status: "pending" }} isActive={false} playlistNames={[]}
      onPlay={onPlay} onToggleFavorite={noop} onAddToPlaylist={noop}
      onNewPlaylist={noop} onDelete={noop} onRetry={noop} />
  );
  fireEvent.click(screen.getByRole("listitem"));
  expect(onPlay).not.toHaveBeenCalled();
});

test("failed song shows Retry, calls onRetry without triggering onPlay", () => {
  const onPlay = jest.fn();
  const onRetry = jest.fn();
  render(
    <SongCard song={{ ...baseSong, status: "failed" }} isActive={false} playlistNames={[]}
      onPlay={onPlay} onToggleFavorite={noop} onAddToPlaylist={noop}
      onNewPlaylist={noop} onDelete={noop} onRetry={onRetry} />
  );
  fireEvent.click(screen.getByLabelText("Retry processing"));
  expect(onRetry).toHaveBeenCalledTimes(1);
  expect(onPlay).not.toHaveBeenCalled();
});

test("active song gets song-card--active class", () => {
  render(
    <SongCard song={baseSong} isActive playlistNames={[]}
      onPlay={noop} onToggleFavorite={noop} onAddToPlaylist={noop}
      onNewPlaylist={noop} onDelete={noop} onRetry={noop} />
  );
  expect(screen.getByRole("listitem")).toHaveClass("song-card--active");
});