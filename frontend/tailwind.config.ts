import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d11",
        panel: "#141821",
        panel2: "#1a1f29",
        rack: "#10141b",
        line: "#232a36",
        line2: "#2c3543",
        ink: "#e6eaf2",
        muted: "#8a95a8",
        faint: "#5c6678",
        cyan: "#2dd4ee",
        blu: "#3b82f6",
        green: "#34d399",
        amber: "#fbbf24",
        red: "#f87171",
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "sans-serif"],
        mono: ["var(--font-plex-mono)", "monospace"],
      },
      keyframes: {
        scpulse: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".45" } },
        scfade: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        scpulse: "scpulse 2s infinite",
        scfade: "scfade .15s ease both",
      },
      backgroundImage: {
        "eng-grid":
          "linear-gradient(#ffffff07 1px,transparent 1px),linear-gradient(90deg,#ffffff07 1px,transparent 1px),linear-gradient(#ffffff04 1px,transparent 1px),linear-gradient(90deg,#ffffff04 1px,transparent 1px)",
      },
      backgroundSize: {
        "eng-grid": "96px 96px,96px 96px,24px 24px,24px 24px",
      },
    },
  },
  plugins: [],
};
export default config;
