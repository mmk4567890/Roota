/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        hud: {
          bg: "#08090B",
          glow: "#16181C",
          surface: "#0D0F12",
          line: "rgba(255,255,255,0.08)",
          "line-hover": "rgba(255,255,255,0.16)",
          text: "#EDEDED",
          muted: "#8B8F97",
          faint: "#5A5F68",
          confirmed: "#4ADE80",
          escalated: "#F87171",
          inconclusive: "#FBBF24",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      maxWidth: {
        content: "960px",
      },
      transitionDuration: {
        hud: "120ms",
      },
      letterSpacing: {
        display: "0.1em",
        label: "0.06em",
      },
      fontSize: {
        12: ["12px", "1.4"],
        14: ["14px", "1.45"],
        16: ["16px", "1.5"],
        20: ["20px", "1.35"],
        32: ["32px", "1.2"],
      },
    },
  },
  plugins: [],
};
