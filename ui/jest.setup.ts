// ui/jest.setup.ts
import "@testing-library/jest-dom";

// jsdom has no real <audio> playback engine — HTMLMediaElement.pause/play
// log "not implemented" console.error noise on every PlayerProvider
// unmount. Harmless (no assertion depends on real playback), but noisy
// across every test file that mounts PlayerProvider. Stub both no-ops.
window.HTMLMediaElement.prototype.pause = () => {};
window.HTMLMediaElement.prototype.play = () => Promise.resolve();

import { server } from "./src/test/server";

// msw lifecycle — same before/after/afterEach pattern regardless of
// which test file is running.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
