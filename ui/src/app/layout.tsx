// ui/src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { ToastProvider } from "@/components/Toast";
import { PlayerProvider } from "@/components/PlayerProvider";
import { PlayerBar } from "@/components/PlayerBar";

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
        <PlayerProvider>
          <ToastProvider>
            <Nav />
            <main className="main">
              <div id="page-content">{children}</div>
            </main>
            <PlayerBar />
          </ToastProvider>
        </PlayerProvider>
      </body>
    </html>
  );
}
