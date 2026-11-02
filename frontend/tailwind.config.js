/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f8f9",
          100: "#eef0f2",
          200: "#d9dde3",
          300: "#b8c0cb",
          400: "#8b97a8",
          500: "#6b7a8d",
          600: "#556274",
          700: "#465060",
          800: "#3c4451",
          900: "#353b46",
          950: "#22262e",
        },
        accent: {
          DEFAULT: "#1f6b5c",
          muted: "#e8f2ef",
        },
      },
      fontFamily: {
        sans: ['"Segoe UI"', '"Helvetica Neue"', "Helvetica", "sans-serif"],
      },
    },
  },
  plugins: [],
};
