/**
 * Ported from app.js: a non-null bookmark alone isn't enough to keep
 * paging — a short page (fewer records than limit) also means end of
 * results, even if the API returned a bookmark.
 */
export function hasMorePages(
  bookmark: string | null,
  recordsLength: number,
  limit: number
): boolean {
  return !!bookmark && recordsLength >= limit;
}