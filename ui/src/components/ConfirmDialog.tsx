import { Modal } from "./Modal";

/**
 * Ported from app.js's confirmDeleteSong()/confirmDeletePlaylist() —
 * same modal shell reused for both (PRD FE7-2 table), built on the
 * generic <Modal> from FE7-2.
 */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Delete",
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal onClose={onCancel} className="confirm-dialog">
      <h2 className="modal__title">{title}</h2>
      <p className="confirm-dialog__msg">{message}</p>
      <div className="modal__footer">
        <button className="btn btn--ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn--danger" onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}