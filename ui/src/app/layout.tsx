import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "melo",
  icons: { icon: "/assets/logo.png" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <Nav />
          <main className="main">
            <div id="page-content">{children}</div>
          </main>
          {/* Static empty-state placeholder — real wiring is FE7-4/FE7-6.
              Kept so the CSS grid's 3 rows (main/player-bar/tab-bar)
              don't collapse before the player exists. */}
          <div className="player-bar player-bar--empty" id="player-bar">
            <div className="player-bar__placeholder">
              <span>No song playing — pick one from your library</span>
            </div>
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}