// ui/src/lib/reorder.ts
// Pure move-item math, ported verbatim from app.js's
// reorderPlaylistSongOptimistic(): splice out at fromIndex, splice in
// at toIndex. Drag-and-keyboard reorder both call this — same "insert
// at final index" semantics DECISIONS.md documents, Karthik-confirmed
// working in the vanilla version, not re-litigated here.
//
// Logic-only test surface per PRD's locked FE7-7 decision — native
// HTML5 dataTransfer is unsupported/flaky in jsdom, so the index math
// is tested directly instead of via simulated drag events.

export function moveItem<T>(
  list: T[],
  fromIndex: number,
  toIndex: number,
): T[] {
  if (fromIndex < 0 || fromIndex >= list.length) return list;
  if (fromIndex === toIndex) return list;

  const result = list.slice();
  // Non-null: fromIndex bounds checked above, splice always returns the element.
  const [moved] = result.splice(fromIndex, 1) as [T];
  const clampedTo = Math.max(0, Math.min(toIndex, result.length));
  result.splice(clampedTo, 0, moved);
  return result;
}
