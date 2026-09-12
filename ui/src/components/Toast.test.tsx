import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "./Toast";

function Trigger({ message, type }: { message: string; type?: "success" | "error" }) {
    const { show } = useToast();
    return <button onClick={() => show(message, type)}>fire</button>;
}

jest.useFakeTimers();

test("shows a toast on demand, auto-dismisses after 3s", () => {
    render(
        <ToastProvider>
            <Trigger message="Added to Melo" />
        </ToastProvider>
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByText("Added to Melo")).toBeInTheDocument();

    act(() => {
        jest.advanceTimersByTime(3000);
    });
    expect(screen.queryByText("Added to Melo")).toBeNull();
});

test("error type gets toast--error class", () => {
    render(
        <ToastProvider>
            <Trigger message="oops" type="error" />
        </ToastProvider>
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByText("oops")).toHaveClass("toast--error");
});

test("useToast outside provider throws", () => {
    // React logs the caught render error to console.error twice (dev-mode
    // double-invoke) — expected noise, not a real failure. Silenced here
    // so test output stays readable.
    const spy = jest.spyOn(console, "error").mockImplementation(() => { });
    const Bad = () => {
        useToast();
        return null;
    };
    expect(() => render(<Bad />)).toThrow();
    spy.mockRestore();
});