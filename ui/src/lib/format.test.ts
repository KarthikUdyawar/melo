import { formatDuration } from "./format";

test("formats seconds as m:ss", () => {
    expect(formatDuration(213)).toBe("3:33");
});

test("empty/null/undefined -> empty string", () => {
    expect(formatDuration(0)).toBe("");
    expect(formatDuration(null)).toBe("");
    expect(formatDuration(undefined)).toBe("");
});
