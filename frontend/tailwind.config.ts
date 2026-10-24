import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101417",
        steel: "#59646E",
        mist: "#E8EBEE",
        line: "#CBD2D8",
        paper: "#FFFFFF",
        signal: "#D6212A",
        signalDark: "#A8171F",
        ok: "#1F7A4D",
      },
      fontFamily: {
        display: ["Bahnschrift", "'DIN Alternate'", "'Roboto Condensed'", "'Arial Narrow'", "system-ui", "sans-serif"],
        sans: ["'Segoe UI'", "system-ui", "-apple-system", "Roboto", "Helvetica", "Arial", "sans-serif"],
        mono: ["'Cascadia Mono'", "Consolas", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
