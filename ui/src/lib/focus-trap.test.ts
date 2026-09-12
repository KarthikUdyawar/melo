import { trapFocus } from "./focus-trap";

function setup() {
    const container = document.createElement("div");
    const a = document.createElement("button");
    const b = document.createElement("button");
    container.append(a, b);
    document.body.appendChild(container);
    return { container, a, b };
}

afterEach(() => {
    document.body.innerHTML = "";
});

test("Tab on last wraps to first", () => {
    const { container, a, b } = setup();
    b.focus();
    const e = new KeyboardEvent("keydown", { key: "Tab" });
    jest.spyOn(e, "preventDefault");
    trapFocus(container, e);
    expect(e.preventDefault).toHaveBeenCalled();
    expect(document.activeElement).toBe(a);
});

test("Shift+Tab on first wraps to last", () => {
    const { container, a, b } = setup();
    a.focus();
    const e = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true });
    jest.spyOn(e, "preventDefault");
    trapFocus(container, e);
    expect(e.preventDefault).toHaveBeenCalled();
    expect(document.activeElement).toBe(b);
});

test("non-Tab key is a no-op", () => {
    const { container, a } = setup();
    a.focus();
    const e = new KeyboardEvent("keydown", { key: "Escape" });
    expect(() => trapFocus(container, e)).not.toThrow();
});