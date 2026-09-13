// ui/src/lib/loop-mode.test.ts
import { cycleLoopMode, type LoopMode } from "./loop-mode";

test("off cycles to one", () => {
  expect(cycleLoopMode("off")).toBe("one");
});

test("one cycles to all", () => {
  expect(cycleLoopMode("one")).toBe("all");
});

test("all cycles to off", () => {
  expect(cycleLoopMode("all")).toBe("off");
});

test("exhaustive: every mode maps to a different mode", () => {
  const modes: LoopMode[] = ["off", "one", "all"];
  modes.forEach((m) => expect(cycleLoopMode(m)).not.toBe(m));
});
