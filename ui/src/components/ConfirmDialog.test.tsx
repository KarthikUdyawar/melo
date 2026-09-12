import { render, screen, fireEvent } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

test("renders title and message", () => {
  render(
    <ConfirmDialog
      title="Delete Song"
      message="Delete this song? This cannot be undone."
      onConfirm={() => {}}
      onCancel={() => {}}
    />
  );
  expect(screen.getByText("Delete Song")).toBeInTheDocument();
  expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
});

test("Delete calls onConfirm, Cancel calls onCancel", () => {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();
  render(
    <ConfirmDialog title="t" message="m" onConfirm={onConfirm} onCancel={onCancel} />
  );
  fireEvent.click(screen.getByText("Delete"));
  expect(onConfirm).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Cancel"));
  expect(onCancel).toHaveBeenCalledTimes(1);
});