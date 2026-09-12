// jsdom's fetch/Request/Response predate what msw@2 expects — polyfill
// with undici's implementations before msw's node server is set up.
const { TextDecoder, TextEncoder } = require("util");

// Must run before importing undici — undici reads these off `global`
// at module-init time. require() (not import) so this actually runs
// first — ES imports get hoisted above all other statements.
const { ReadableStream, TransformStream, WritableStream } = require("stream/web");
Object.assign(global, { TextDecoder, TextEncoder, ReadableStream, TransformStream, WritableStream });

const { fetch, Headers, Request, Response } = require("undici");

Object.assign(global, {
    fetch,
    Headers,
    Request,
    Response,
});

const { BroadcastChannel } = require("worker_threads");
Object.assign(global, { BroadcastChannel });