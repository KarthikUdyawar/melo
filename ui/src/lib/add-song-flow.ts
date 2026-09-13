// Pure step-machine for AddSongModal: url -> loading -> preview.
// Logic-only tested; component stays thin fetch/render glue — same
// split as FE7-4's player-reducer.ts.
// ui/src/lib/add-song-flow.ts

import type { SongPreview } from "./types";

export type AddSongStep = "url" | "loading" | "preview";

export interface AddSongState {
  step: AddSongStep;
  url: string;
  error: string | null;
  preview: SongPreview | null;
  start: string;
  end: string;
  speed: string;
}

export type AddSongAction =
  | { type: "SET_URL"; url: string }
  | { type: "SUBMIT" }
  | { type: "PREVIEW_SUCCESS"; preview: SongPreview }
  | { type: "PREVIEW_ERROR"; message: string }
  | { type: "SET_PARAM"; field: "start" | "end" | "speed"; value: string }
  | { type: "RESET" };

export const initialAddSongState: AddSongState = {
  step: "url",
  url: "",
  error: null,
  preview: null,
  start: "",
  end: "",
  speed: "1.0",
};

export function addSongReducer(
  state: AddSongState,
  action: AddSongAction,
): AddSongState {
  switch (action.type) {
    case "SET_URL":
      return { ...state, url: action.url, error: null };
    case "SUBMIT":
      return { ...state, step: "loading", error: null };
    case "PREVIEW_SUCCESS":
      return {
        ...state,
        step: "preview",
        preview: action.preview,
        error: null,
      };
    case "PREVIEW_ERROR":
      return { ...state, step: "url", error: action.message };
    case "SET_PARAM":
      return { ...state, [action.field]: action.value };
    case "RESET":
      return initialAddSongState;
    default:
      return state;
  }
}
