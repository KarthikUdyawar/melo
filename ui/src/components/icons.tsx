// ui/src/components/icons.tsx
// Shared transport/volume icons — inline SVG, no icon-lib dep.
// currentColor so existing hover/active color rules apply unchanged.

export function PlayIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <path d="M3 2l11 6-11 6V2z" />
    </svg>
  );
}

export function PauseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <rect x="3" y="2" width="4" height="12" />
      <rect x="9" y="2" width="4" height="12" />
    </svg>
  );
}

export function PrevIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <rect x="2" y="2" width="2" height="12" />
      <path d="M14 2L4 8l10 6V2z" />
    </svg>
  );
}

export function NextIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <rect x="12" y="2" width="2" height="12" />
      <path d="M2 2l10 6-10 6V2z" />
    </svg>
  );
}

export function ShuffleIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 5h3.5c1.4 0 2.6.75 3.3 1.9L12 12.5c.7 1.15 1.9 1.9 3.3 1.9H17" />
      <path d="M14.5 4.5L17 2v5l-2.5-2.5z" />
      <path d="M2 15h3.5c1.4 0 2.6-.75 3.3-1.9" />
      <path d="M14.5 15.5L17 18v-5l-2.5 2.5z" />
    </svg>
  );
}

export function LoopIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 8V6a2 2 0 0 1 2-2h9" />
      <path d="M12.5 1.5L15 4l-2.5 2.5" />
      <path d="M16 12v2a2 2 0 0 1-2 2H5" />
      <path d="M7.5 18.5L5 16l2.5-2.5" />
    </svg>
  );
}

export function VolumeIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8h3l5-4v12l-5-4H3V8z" fill="currentColor" stroke="none" />
      <path d="M13.5 6.5a5 5 0 0 1 0 7" />
      <path d="M15.8 4.2a8.5 8.5 0 0 1 0 11.6" />
    </svg>
  );
}

export function MuteIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8h3l5-4v12l-5-4H3V8z" fill="currentColor" stroke="none" />
      <path d="M13.5 7l4 4M17.5 7l-4 4" />
    </svg>
  );
}
