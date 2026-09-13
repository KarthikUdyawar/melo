// ui/src/app/playlists/page.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import PlaylistsPage from "./page";
import { ToastProvider } from "@/components/Toast";

const push = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function renderPage() {
  return render(
    <ToastProvider>
      <PlaylistsPage />
    </ToastProvider>,
  );
}

describe("PlaylistsPage", () => {
  it("empty state, then creates a playlist via inline input", async () => {
    server.use(
      http.post("/api/playlists", () =>
        HttpResponse.json(
          {
            status_code: 201,
            message: "ok",
            body: { id: "p1", name: "Mix", created_at: "t", song_count: 0 },
          },
          { status: 201 },
        ),
      ),
    );
    renderPage();
    expect(await screen.findByText("No playlists yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("+ New Playlist"));
    fireEvent.change(screen.getByPlaceholderText("Playlist name…"), {
      target: { value: "Mix" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Playlist name…"), {
      key: "Enter",
    });
    await waitFor(() =>
      expect(
        screen.queryByPlaceholderText("Playlist name…"),
      ).not.toBeInTheDocument(),
    );
  });

  it("deletes a playlist via confirm dialog", async () => {
    let getCallCount = 0;
    server.use(
      // First GET (mount) returns the playlist; refresh() after delete
      // must reflect it actually being gone, not repeat the same body —
      // a stateless mock here would make the empty-state assertion
      // meaningless (it'd pass even if delete/refresh were never wired).
      http.get("/api/playlists", () => {
        getCallCount++;
        const records =
          getCallCount === 1
            ? [{ id: "p1", name: "Mix", created_at: "t", song_count: 1 }]
            : [];
        return HttpResponse.json({
          status_code: 200,
          message: "ok",
          body: { records, count: records.length, bookmark: null },
        });
      }),
      http.delete(
        "/api/playlists/:id",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    renderPage();
    fireEvent.click(await screen.findByLabelText(/delete/i));
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() =>
      expect(screen.getByText("No playlists yet.")).toBeInTheDocument(),
    );
  });
});
