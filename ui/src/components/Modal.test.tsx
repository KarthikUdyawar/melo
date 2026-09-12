import { render, screen, fireEvent } from "@testing-library/react";
import { Modal } from "./Modal";

test("Escape calls onClose", () => {
  const onClose = jest.fn();
  render(
    <Modal onClose={onClose}>
      <button>inside</button>
    </Modal>
  );
  fireEvent.keyDown(document, { key: "Escape" });
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("click on overlay (not content) calls onClose", () => {
  const onClose = jest.fn();
  const { container } = render(
    <Modal onClose={onClose}>
      <button>inside</button>
    </Modal>
  );
  fireEvent.click(container.querySelector(".modal-overlay")!);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("click inside content does not close", () => {
  const onClose = jest.fn();
  render(
    <Modal onClose={onClose}>
      <button>inside</button>
    </Modal>
  );
  fireEvent.click(screen.getByText("inside"));
  expect(onClose).not.toHaveBeenCalled();
});