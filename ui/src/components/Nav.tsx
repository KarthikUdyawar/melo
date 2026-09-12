"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ROUTES = [
  { href: "/", label: "Library" },
  { href: "/favorites", label: "Favorites" },
  { href: "/playlists", label: "Playlists" },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

/**
 * Sidebar (tablet/desktop) + bottom tab bar (phone) — same 3 routes,
 * chrome differs by breakpoint per DESIGN.md's App Shell. Real <Link>
 * routing replaces the old hash router; active state via usePathname
 * replaces the old window.location.hash check.
 *
 * Add Song button is a stub — FE7-8 wires the actual modal.
 */
export function Nav() {
  const pathname = usePathname();

  const links = ROUTES.map((r) => (
    <Link
      key={r.href}
      href={r.href}
      className={`nav-link${isActive(pathname, r.href) ? " nav-link--active" : ""}`}
    >
      <span className="nav-link__label">{r.label}</span>
    </Link>
  ));

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar__logo">
          <img className="sidebar__logo-mark" src="/assets/logo.png" alt="Melo" />
          <span className="sidebar__logo-full">melo</span>
        </div>
        <nav className="sidebar__nav">{links}</nav>
        <button
          className="btn btn--accent sidebar__add btn-add-song-trigger"
          aria-label="Add song"
          title="Coming in FE7-8"
          aria-disabled="true"
        >
          <span className="sidebar__add-icon" aria-hidden="true">+</span>
          <span className="sidebar__add-label">Add Song</span>
        </button>
      </aside>

      <button
        className="fab-add btn-add-song-trigger"
        aria-label="Add song"
        title="Coming in FE7-8"
        aria-disabled="true"
      >
        +
      </button>

      <nav className="tab-bar" aria-label="Primary">
        {ROUTES.map((r) => (
          <Link
            key={r.href}
            href={r.href}
            className={`nav-link tab-bar__link${isActive(pathname, r.href) ? " nav-link--active" : ""}`}
          >
            <span className="nav-link__label">{r.label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}