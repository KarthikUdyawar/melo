import { moveItem } from "./reorder";

describe("moveItem", () => {
  it("moves an item down (splice out, splice in at target)", () => {
    expect(moveItem(["A", "B", "C", "D"], 0, 2)).toEqual(["B", "C", "A", "D"]);
  });

  it("moves an item up (splice out, splice in at target)", () => {
    expect(moveItem(["A", "B", "C", "D"], 3, 1)).toEqual(["A", "D", "B", "C"]);
  });

  it("is a no-op when fromIndex === toIndex", () => {
    const list = ["A", "B", "C"];
    expect(moveItem(list, 1, 1)).toEqual(list);
  });

  it("is a no-op when fromIndex is out of range", () => {
    const list = ["A", "B", "C"];
    expect(moveItem(list, -1, 0)).toEqual(list);
    expect(moveItem(list, 5, 0)).toEqual(list);
  });

  it("clamps toIndex below 0", () => {
    expect(moveItem(["A", "B", "C"], 2, -5)).toEqual(["C", "A", "B"]);
  });

  it("clamps toIndex past the end", () => {
    expect(moveItem(["A", "B", "C"], 0, 99)).toEqual(["B", "C", "A"]);
  });

  it("does not mutate the input array", () => {
    const list = ["A", "B", "C"];
    const snapshot = [...list];
    moveItem(list, 0, 2);
    expect(list).toEqual(snapshot);
  });

  it("preserves length", () => {
    const list = ["A", "B", "C", "D", "E"];
    expect(moveItem(list, 1, 3)).toHaveLength(list.length);
  });
});
