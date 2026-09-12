/**
 * Ported from app.js's trapFocus(). Pure DOM logic, no React —
 * shared by Modal and (later) the Now Playing panel, same as the
 * vanilla version's shared function taking the container as a param.
 */
export function trapFocus(container: HTMLElement, e: KeyboardEvent): void {
  if (e.key !== "Tab") return;

  const focusables = Array.from(
    container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
  ).filter((el) => !(el as HTMLButtonElement).disabled);
  // NOTE: no offsetParent/visibility check here — jsdom has no layout
  // engine, offsetParent is always null there, which silently emptied
  // this list in tests. Real hidden-element filtering (if ever needed)
  // should check `.hidden` / computed display, not offsetParent.

  if (!focusables.length) return;
  // Non-null: length check above guarantees both indices exist; TS's
  // array indexing can't narrow that on its own.
  const first = focusables[0]!;
  const last = focusables[focusables.length - 1]!;

  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}