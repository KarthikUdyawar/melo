import { render, screen, fireEvent } from "@testing-library/react";
import { SongCardMenu } from "./SongCardMenu";

function setup(playlistNames = ["Mix"]) {
  const props = {
    playlistNames,
    onAddToPlaylist: jest.fn(),
    onNewPlaylist: jest.fn(),
    onDelete: jest.fn(),
  };
  render(<SongCardMenu {...props} />);
  return props;
}

describe("SongCardMenu", () => {
  it("opens on trigger click, syncs aria-expanded", () => {
    setup();
    const trigger = screen.getByLabelText("More options");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("lists playlist names, calls onAddToPlaylist and closes", () => {
    const props = setup();
    fireEvent.click(screen.getByLabelText("More options"));
    fireEvent.click(screen.getByText("Mix"));
    expect(props.onAddToPlaylist).toHaveBeenCalledWith("Mix");
    expect(screen.queryByText("Mix")).not.toBeInTheDocument();
  });

  it("calls onNewPlaylist from the + New playlist item", () => {
    const props = setup();
    fireEvent.click(screen.getByLabelText("More options"));
    fireEvent.click(screen.getByText("+ New playlist"));
    expect(props.onNewPlaylist).toHaveBeenCalled();
  });

  it("calls onDelete from the destructive item", () => {
    const props = setup();
    fireEvent.click(screen.getByLabelText("More options"));
    fireEvent.click(screen.getByText("Delete"));
    expect(props.onDelete).toHaveBeenCalled();
  });

  it("closes on outside click", () => {
    setup();
    fireEvent.click(screen.getByLabelText("More options"));
    expect(screen.getByText("Delete")).toBeInTheDocument();
    fireEvent.click(document.body);
    expect(screen.queryByText("Delete")).not.toBeInTheDocument();
  });
});
