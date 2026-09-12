import "@testing-library/jest-dom";
import { server } from "./src/test/server";

// msw lifecycle — same before/after/afterEach pattern regardless of
// which test file is running.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
