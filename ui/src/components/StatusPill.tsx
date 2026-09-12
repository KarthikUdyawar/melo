import type { SongStatus } from "@/lib/types";

/** 1:1 port of components.js's renderStatusPill(). */
export function StatusPill({ status }: { status: SongStatus }) {
  if (status === "done") return null;

  const pulse = status === "processing" ? " status-dot--pulse" : "";

  return (
    <span
      className={`status-pill status-pill--${status}`}
      aria-label={`Status: ${status}`}
    >
      <span className={`status-dot${pulse}`} aria-hidden="true" />
      {status}
    </span>
  );
}