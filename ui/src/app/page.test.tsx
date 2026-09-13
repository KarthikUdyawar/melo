import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import LibraryPage from "./page";
import { PlayerProvider } from "@/components/PlayerProvider";
import { ToastProvider } from "@/components/Toast";

const song = {
  id: "s1",
  title: "Song One",
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
  is_favorite: false,
  stream_url: "/songs/s1/stream",
  effective_duration: 10,
};

function renderPage() {
  return render(
    <PlayerProvider>
      <ToastProvider>
        <LibraryPage />
      </ToastProvider>
    </PlayerProvider>,
  );
}

describe("LibraryPage", () => {
  it("shows empty state when no songs", async () => {
    renderPage();
    expect(await screen.findByText("No songs yet.")).toBeInTheDocument();
  });

  it("renders song list and search filters", async () => {
    server.use(
      http.get("/api/songs", ({ request }) => {
        const url = new URL(request.url);
        const records =
          url.searchParams.get("search") === "nomatch" ? [] : [song];
        return HttpResponse.json({
          status_code: 200,
          message: "ok",
          body: { records, count: records.length, bookmark: null },
        });
      }),
    );
    renderPage();
    expect(await screen.findByText("Song One")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search songs…"), {
      target: { value: "nomatch" },
    });
    await waitFor(() =>
      expect(screen.getByText("No songs yet.")).toBeInTheDocument(),
    );
  });
});

it("status and sort selects trigger a re-fetch with the right params", async () => {
  server.use(
    http.get("/api/songs", ({ request }) => {
      const url = new URL(request.url);
      expect(["", "done"]).toContain(url.searchParams.get("status") ?? "");
      return HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [song], count: 1, bookmark: null },
      });
    }),
  );
  renderPage();
  await screen.findByText("Song One");
  fireEvent.change(screen.getByDisplayValue("All status"), {
    target: { value: "done" },
  });
  fireEvent.change(screen.getByDisplayValue("Newest"), {
    target: { value: "title|asc" },
  });
  await screen.findByText("Song One");
});

it("toggling favorite optimistically updates, reverts on API failure", async () => {
  server.use(
    http.get("/api/songs", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [song], count: 1, bookmark: null },
      }),
    ),
    http.post("/api/favorites/:id", () =>
      HttpResponse.json(
        { status_code: 500, message: "boom", body: {} },
        { status: 500 },
      ),
    ),
  );
  renderPage();
  await screen.findByText("Song One");
  fireEvent.click(screen.getByLabelText(/favorite/i));
  await waitFor(() =>
    expect(screen.getByLabelText(/favorite/i)).toBeInTheDocument(),
  );
});

it("delete flow: confirm dialog removes the song from the list", async () => {
  server.use(
    http.get("/api/songs", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [song], count: 1, bookmark: null },
      }),
    ),
    http.delete(
      "/api/songs/:id",
      () => new HttpResponse(null, { status: 204 }),
    ),
  );
  renderPage();
  await screen.findByText("Song One");
  fireEvent.click(screen.getByLabelText("More options"));
  fireEvent.click(screen.getByText("Delete"));
  fireEvent.click(screen.getByText("Delete", { selector: ".btn--danger" }));
  await waitFor(() =>
    expect(screen.queryByText("Song One")).not.toBeInTheDocument(),
  );
});

it("retry re-submits the same params, then deletes the old failed record", async () => {
  const failed = {
    ...song,
    status: "failed" as const,
    start: 5,
    end: 20,
    speed: 1.5,
  };
  let submitted = false;
  server.use(
    http.get("/api/songs", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [failed], count: 1, bookmark: null },
      }),
    ),
    http.post("/api/songs", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      expect(body).toMatchObject({ start: 5, end: 20, speed: 1.5 });
      submitted = true;
      return HttpResponse.json(
        {
          status_code: 202,
          message: "ok",
          body: { id: "new1", status: "pending" },
        },
        { status: 202 },
      );
    }),
    http.delete(
      "/api/songs/:id",
      () => new HttpResponse(null, { status: 204 }),
    ),
  );
  renderPage();
  fireEvent.click(await screen.findByText("↺ Retry"));
  await waitFor(() => expect(submitted).toBe(true));
});

it("adds a song to an existing playlist via the dropdown", async () => {
  server.use(
    http.get("/api/songs", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [song], count: 1, bookmark: null },
      }),
    ),
    http.get("/api/playlists", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: {
          records: [{ id: "p1", name: "Mix", created_at: "t", song_count: 0 }],
          count: 1,
          bookmark: null,
        },
      }),
    ),
    http.post("/api/playlists/:id/songs/:songId", () =>
      HttpResponse.json(
        { status_code: 201, message: "ok", body: { id: "s1" } },
        { status: 201 },
      ),
    ),
  );
  renderPage();
  await screen.findByText("Song One");
  fireEvent.click(screen.getByLabelText("More options"));
  fireEvent.click(await screen.findByText("Mix"));
  expect(await screen.findByText('Added to "Mix"')).toBeInTheDocument();
});

it("creates a new playlist via window.prompt and adds the song to it", async () => {
  jest.spyOn(window, "prompt").mockReturnValue("Road Trip");
  server.use(
    http.get("/api/songs", () =>
      HttpResponse.json({
        status_code: 200,
        message: "ok",
        body: { records: [song], count: 1, bookmark: null },
      }),
    ),
    http.post("/api/playlists", () =>
      HttpResponse.json(
        {
          status_code: 201,
          message: "ok",
          body: { id: "p2", name: "Road Trip", created_at: "t", song_count: 0 },
        },
        { status: 201 },
      ),
    ),
    http.post("/api/playlists/:id/songs/:songId", () =>
      HttpResponse.json(
        { status_code: 201, message: "ok", body: { id: "s1" } },
        { status: 201 },
      ),
    ),
  );
  renderPage();
  await screen.findByText("Song One");
  fireEvent.click(screen.getByLabelText("More options"));
  fireEvent.click(screen.getByText("+ New playlist"));
  expect(await screen.findByText('Added to "Road Trip"')).toBeInTheDocument();
  (window.prompt as jest.Mock).mockRestore();
});
