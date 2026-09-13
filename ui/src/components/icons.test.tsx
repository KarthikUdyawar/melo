// ui/src/components/icons.test.tsx
// Smoke coverage for icons.tsx — pure SVG components, no props/state,
// nothing to assert beyond "renders without throwing." Matches the
// treatment other zero-logic leaf components (StatusPill etc.) get.

import { render } from "@testing-library/react";
import {
  PlayIcon,
  PauseIcon,
  PrevIcon,
  NextIcon,
  ShuffleIcon,
  LoopIcon,
  VolumeIcon,
  MuteIcon,
} from "./icons";

describe("icons", () => {
  const icons = [
    PlayIcon,
    PauseIcon,
    PrevIcon,
    NextIcon,
    ShuffleIcon,
    LoopIcon,
    VolumeIcon,
    MuteIcon,
  ];

  it.each(icons.map((Icon) => [Icon.name, Icon]))(
    "%s renders an svg",
    (_name, Icon) => {
      const { container } = render(<Icon />);
      expect(container.querySelector("svg")).toBeInTheDocument();
    },
  );
});
