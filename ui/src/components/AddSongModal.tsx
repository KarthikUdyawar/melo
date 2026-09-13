"use client";

// 2-step flow ported from app.js's buildStep1Html/showStep2. Step
// transitions live in lib/add-song-flow.ts (tested); this is fetch+
// render glue only.
// ui/src/components/AddSongModal.tsx

import { useReducer } from "react";
import Image from "next/image";
import { Modal } from "./Modal";
import { useToast } from "./Toast";
import { previewSong, submitSong } from "@/lib/api";
import { addSongReducer, initialAddSongState } from "@/lib/add-song-flow";
import { formatDuration } from "@/lib/format";
import { ApiError } from "@/lib/types";

export function AddSongModal({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useReducer(addSongReducer, initialAddSongState);
  const toast = useToast();

  async function handlePreview() {
    dispatch({ type: "SUBMIT" });
    try {
      const preview = await previewSong(state.url);
      dispatch({ type: "PREVIEW_SUCCESS", preview });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not fetch preview.";
      dispatch({ type: "PREVIEW_ERROR", message });
    }
  }

  async function handleAdd() {
    try {
      await submitSong({
        url: state.url,
        start: state.start ? Number(state.start) : undefined,
        end: state.end ? Number(state.end) : undefined,
        speed: state.speed ? Number(state.speed) : undefined,
      });
      toast.show("Added to Melo");
      onClose();
    } catch {
      toast.show("Could not add song.", "error");
    }
  }

  return (
    <Modal onClose={onClose}>
      {state.step !== "preview" ? (
        <div className="modal__step">
          <label htmlFor="add-song-url">Paste YouTube URL</label>
          <input
            id="add-song-url"
            type="text"
            value={state.url}
            disabled={state.step === "loading"}
            onChange={(e) => dispatch({ type: "SET_URL", url: e.target.value })}
            placeholder="https://youtube.com/..."
          />
          {state.error && <p className="modal__error">{state.error}</p>}
          <button
            className="btn btn--accent"
            disabled={!state.url || state.step === "loading"}
            onClick={handlePreview}
          >
            {state.step === "loading" ? (
              <>
                <span className="spinner" aria-hidden="true" /> Fetching…
              </>
            ) : (
              "Preview"
            )}
          </button>
        </div>
      ) : (
        <div className="modal__step">
          <div className="modal__preview-header">
            <Image
              src={state.preview!.thumbnail_url}
              alt=""
              width={64}
              height={64}
              unoptimized
            />
            <div>
              <p>{state.preview!.title}</p>
              <p className="text-secondary">
                {state.preview!.channel} ·{" "}
                {formatDuration(state.preview!.duration)}
              </p>
            </div>
          </div>

          <label htmlFor="add-song-start">Start</label>
          <input
            id="add-song-start"
            type="number"
            value={state.start}
            onChange={(e) =>
              dispatch({
                type: "SET_PARAM",
                field: "start",
                value: e.target.value,
              })
            }
          />
          <label htmlFor="add-song-end">End</label>
          <input
            id="add-song-end"
            type="number"
            value={state.end}
            onChange={(e) =>
              dispatch({
                type: "SET_PARAM",
                field: "end",
                value: e.target.value,
              })
            }
          />
          <label htmlFor="add-song-speed">Speed</label>
          <select
            id="add-song-speed"
            value={state.speed}
            onChange={(e) =>
              dispatch({
                type: "SET_PARAM",
                field: "speed",
                value: e.target.value,
              })
            }
          >
            {["0.5", "0.75", "1.0", "1.25", "1.5", "2.0"].map((v) => (
              <option key={v} value={v}>
                {v}×
              </option>
            ))}
          </select>

          <div className="modal__actions">
            <button className="btn" onClick={onClose}>
              Cancel
            </button>
            <button className="btn btn--accent" onClick={handleAdd}>
              Add to Melo
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
