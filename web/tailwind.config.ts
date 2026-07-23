import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Booking.com-inspired blue palette (primary action + accents).
        brand: {
          50: "#e7f1fb",
          100: "#cfe4f7",
          200: "#a6ccef",
          300: "#6faede",
          400: "#3a8fd0",
          500: "#0071c2",
          600: "#005ea6",
          700: "#00487f",
        },
        // Booking dark navy (header bar / deep accents).
        navy: {
          DEFAULT: "#003b95",
          dark: "#00224e",
          light: "#013e9c",
        },
        // Booking signature yellow (secondary CTA / highlights).
        accent: {
          DEFAULT: "#febb02",
          600: "#e5a800",
        },
        teal: { 500: "#0097A7" },
        ink: "#1a1a1a",
        line: "#e0e0e0",
        canvas: "#f2f6fb",
      },
      fontFamily: {
        sans: ["Inter", "Poppins", "Segoe UI", "system-ui", "sans-serif"],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
