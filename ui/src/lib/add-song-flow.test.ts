import { addSongReducer, initialAddSongState } from "./add-song-flow";

describe("addSongReducer", () => {
  it("SET_URL updates url, clears error", () => {
    const s = { ...initialAddSongState, error: "bad" };
    const next = addSongReducer(s, {
      type: "SET_URL",
      url: "https://youtu.be/x",
    });
    expect(next.url).toBe("https://youtu.be/x");
    expect(next.error).toBeNull();
  });

  it("SUBMIT moves to loading, clears error", () => {
    const s = { ...initialAddSongState, error: "bad" };
    const next = addSongReducer(s, { type: "SUBMIT" });
    expect(next.step).toBe("loading");
    expect(next.error).toBeNull();
  });

  it("PREVIEW_SUCCESS moves to preview step, stores preview", () => {
    const preview = {
      youtube_id: "x",
      title: "T",
      duration: 10,
      thumbnail_url: "u",
      channel: "C",
      upload_date: "2024-01-01",
    };
    const s = { ...initialAddSongState, step: "loading" as const };
    const next = addSongReducer(s, { type: "PREVIEW_SUCCESS", preview });
    expect(next.step).toBe("preview");
    expect(next.preview).toEqual(preview);
  });

  it("PREVIEW_ERROR returns to url step with message, retry-able", () => {
    const s = { ...initialAddSongState, step: "loading" as const };
    const next = addSongReducer(s, {
      type: "PREVIEW_ERROR",
      message: "Invalid URL",
    });
    expect(next.step).toBe("url");
    expect(next.error).toBe("Invalid URL");
  });

  it("SET_PARAM updates only the named field", () => {
    const next = addSongReducer(initialAddSongState, {
      type: "SET_PARAM",
      field: "start",
      value: "10",
    });
    expect(next.start).toBe("10");
    expect(next.end).toBe("");
    expect(next.speed).toBe("1.0");
  });

  it("RESET returns to initial state regardless of current state", () => {
    const s = {
      ...initialAddSongState,
      step: "preview" as const,
      url: "x",
      error: "e",
    };
    expect(addSongReducer(s, { type: "RESET" })).toEqual(initialAddSongState);
  });

  it("unknown action is a no-op", () => {
    // @ts-expect-error testing default branch
    expect(addSongReducer(initialAddSongState, { type: "NOPE" })).toBe(
      initialAddSongState,
    );
  });
});
