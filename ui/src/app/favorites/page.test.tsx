import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import FavoritesPage from "./page";
import { PlayerProvider } from "@/components/PlayerProvider";
import { ToastProvider } from "@/components/Toast";

const song = {
  id: "s1",
  title: "Fave",
  youtube_id: "x",
  file_url: "f",
  duration: 10,
  start: null,
  end: null,
  speed: 1.0,
  status: "done",
  thumbnail_url: null,
  channel: "C",
  upload_date: "2024-01-01",
  created_at: "2024-01-01T00:00:00",
  is_favorite: true,
  stream_url: "/songs/s1/stream",
  effective_duration: 10,
};

function renderPage() {
  return render(
    <PlayerProvider>
      <ToastProvider>
        <FavoritesPage />
      </ToastProvider>
    </PlayerProvider>,
  );
}

describe("FavoritesPage", () => {
  it("empty state when no favorites", async () => {
    renderPage();
    expect(await screen.findByText("No favorites yet.")).toBeInTheDocument();
  });

  it("un-favoriting removes the song from the list", async () => {
    server.use(
      http.get("/api/favorites", () =>
        HttpResponse.json({
          status_code: 200,
          message: "ok",
          body: { records: [song], count: 1, bookmark: null },
        }),
      ),
      http.delete(
        "/api/favorites/:id",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    renderPage();
    expect(await screen.findByText("Fave")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/favorite/i));
    await waitFor(() =>
      expect(screen.queryByText("Fave")).not.toBeInTheDocument(),
    );
  });
});
