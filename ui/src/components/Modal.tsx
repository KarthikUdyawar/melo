"use client";

import { useEffect, useRef } from "react";
import { trapFocus } from "@/lib/focus-trap";

/**
 * Generic modal shell — overlay + focus trap + Escape-to-close.
 * FE7-8's AddSongModal/ConfirmDialog build their content inside this,
 * same relationship as the old .modal / trapFocus() pairing in app.js.
 */
export function Modal({
  onClose,
  children,
  className = "",
}: {
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKeydown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (ref.current) trapFocus(ref.current, e);
    };
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`modal ${className}`} ref={ref}>
        {children}
      </div>
    </div>
  );
}