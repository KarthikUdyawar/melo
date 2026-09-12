import type { Config } from "tailwindcss";

// Ported from DESIGN.md's :root tokens — values unchanged, just moved
// from CSS custom properties into Tailwind's theme so classes like
// bg-surface/text-primary/font-display/rounded-md become available.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-base": "#0e0e0e",
        "bg-surface": "#161616",
        "bg-elevated": "#1f1f1f",
        border: "#2a2a2a",
        "text-primary": "#f0f0f0",
        "text-secondary": "#8a8a8a",
        "text-muted": "#484848",
        accent: "#c8f04e",
        "accent-dim": "#8aaa2a",
        danger: "#e05252",
        "player-bg": "#111111",
      },
      fontFamily: {
        display: ["Syne", "sans-serif"],
        body: ["DM Mono", "monospace"],
      },
      spacing: {
        13: "48px", // --space-12 equivalent slot; Tailwind's default scale
        // already covers 4/8/12/16/24/32/64px (1/2/3/4/6/8/16), so most
        // --space-N tokens map straight onto Tailwind's built-in scale
        // without a custom entry — only genuinely non-standard values go here.
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};

export default config;