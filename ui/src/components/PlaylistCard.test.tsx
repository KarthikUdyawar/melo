import { render, screen, fireEvent } from "@testing-library/react";
import { PlaylistCard } from "./PlaylistCard";
import type { Playlist } from "@/lib/types";

const playlist: Playlist = {
  id: "1",
  name: "Morning Mix",
  created_at: "2024-01-01T00:00:00",
  song_count: 3,
};

test("card click calls onOpen", () => {
  const onOpen = jest.fn();
  render(<PlaylistCard playlist={playlist} onOpen={onOpen} onDelete={() => {}} />);
  fireEvent.click(screen.getByRole("listitem"));
  expect(onOpen).toHaveBeenCalledTimes(1);
});

test("delete button calls onDelete, not onOpen", () => {
  const onOpen = jest.fn();
  const onDelete = jest.fn();
  render(<PlaylistCard playlist={playlist} onOpen={onOpen} onDelete={onDelete} />);
  fireEvent.click(screen.getByLabelText("Delete playlist"));
  expect(onDelete).toHaveBeenCalledTimes(1);
  expect(onOpen).not.toHaveBeenCalled();
});

test("singular 'song' at count 1", () => {
  render(<PlaylistCard playlist={{ ...playlist, song_count: 1 }} onOpen={() => {}} onDelete={() => {}} />);
  expect(screen.getByText("1 song")).toBeInTheDocument();
});