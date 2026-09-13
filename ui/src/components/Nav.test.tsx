// ui/src/components/Nav.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { Nav } from "./Nav";
import { ToastProvider } from "./Toast";

jest.mock("next/navigation", () => ({ usePathname: () => "/favorites" }));

// AddSongModal (opened from Nav's triggers) calls useToast() — needs a
// real provider in the tree, same as it gets from layout.tsx in prod.
function renderNav() {
  return render(
    <ToastProvider>
      <Nav />
    </ToastProvider>,
  );
}

describe("Nav", () => {
  it("marks the current route active", () => {
    renderNav();
    const links = screen.getAllByText("Favorites");
    expect(links[0].closest("a")).toHaveClass("nav-link--active");
  });

  it("does not mark other routes active", () => {
    renderNav();
    const links = screen.getAllByText("Library");
    expect(links[0].closest("a")).not.toHaveClass("nav-link--active");
  });

  it("opens AddSongModal from the sidebar trigger", () => {
    renderNav();
    fireEvent.click(
      screen.getByLabelText("Add song", { selector: ".sidebar__add" }),
    );
    expect(screen.getByText("Paste YouTube URL")).toBeInTheDocument();
  });

  it("opens AddSongModal from the FAB trigger", () => {
    renderNav();
    fireEvent.click(
      screen.getByLabelText("Add song", { selector: ".fab-add" }),
    );
    expect(screen.getByText("Paste YouTube URL")).toBeInTheDocument();
  });
});
