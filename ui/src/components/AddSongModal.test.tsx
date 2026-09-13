import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import { AddSongModal } from "./AddSongModal";
import { ToastProvider } from "./Toast";

function renderModal() {
  return render(
    <ToastProvider>
      <AddSongModal onClose={jest.fn()} />
    </ToastProvider>,
  );
}

describe("AddSongModal", () => {
  it("shows inline error on 422 and re-enables the field for retry", async () => {
    server.use(
      http.post("/api/songs/preview", () =>
        HttpResponse.json(
          { status_code: 422, message: "Invalid YouTube URL", body: {} },
          { status: 422 },
        ),
      ),
    );
    renderModal();
    fireEvent.change(screen.getByLabelText("Paste YouTube URL"), {
      target: { value: "bad-url" },
    });
    fireEvent.click(screen.getByText("Preview"));
    expect(await screen.findByText("Invalid YouTube URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Paste YouTube URL")).not.toBeDisabled();
  });

  it("advances to step 2 preview on success, then submits", async () => {
    server.use(
      http.post("/api/songs/preview", () =>
        HttpResponse.json({
          status_code: 200,
          message: "ok",
          body: {
            youtube_id: "x",
            title: "T",
            duration: 10,
            thumbnail_url: "http://x/t.jpg",
            channel: "C",
            upload_date: "2024-01-01",
          },
        }),
      ),
      http.post("/api/songs", () =>
        HttpResponse.json(
          {
            status_code: 202,
            message: "ok",
            body: { id: "s1", status: "pending" },
          },
          { status: 202 },
        ),
      ),
    );
    const onClose = jest.fn();
    render(
      <ToastProvider>
        <AddSongModal onClose={onClose} />
      </ToastProvider>,
    );
    fireEvent.change(screen.getByLabelText("Paste YouTube URL"), {
      target: { value: "https://youtu.be/x" },
    });
    fireEvent.click(screen.getByText("Preview"));
    expect(await screen.findByText("T")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Add to Melo"));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
