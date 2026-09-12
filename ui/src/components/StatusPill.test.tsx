import { render, screen } from "@testing-library/react";
import { StatusPill } from "./StatusPill";

test("done renders nothing", () => {
  const { container } = render(<StatusPill status="done" />);
  expect(container).toBeEmptyDOMElement();
});

test("pending renders pill with aria-label, no pulse", () => {
  render(<StatusPill status="pending" />);
  const pill = screen.getByLabelText("Status: pending");
  expect(pill).toHaveTextContent("pending");
  expect(pill.querySelector(".status-dot--pulse")).toBeNull();
});

test("processing pulses", () => {
  render(<StatusPill status="processing" />);
  expect(screen.getByLabelText("Status: processing").querySelector(".status-dot--pulse")).not.toBeNull();
});

test("failed renders", () => {
  render(<StatusPill status="failed" />);
  expect(screen.getByLabelText("Status: failed")).toHaveTextContent("failed");
});