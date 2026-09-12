import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// One shared msw server for all lib/api.ts tests. Individual tests
// override handlers per-case via server.use(...) for error paths.
export const server = setupServer(...handlers);