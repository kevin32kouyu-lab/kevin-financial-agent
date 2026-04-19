/** 统一 Tailwind 扫描范围与主题扩展配置。 */
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./web/index.html", "./web/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        glass: "0 20px 60px rgba(5, 14, 30, 0.35)",
      },
      colors: {
        terminal: {
          950: "#050b16",
          900: "#0a1324",
          800: "#0f1f36",
          700: "#133055",
          500: "#1f6d8f",
          400: "#3da4c2",
          300: "#76d0de",
          200: "#b9edf2",
        },
      },
      keyframes: {
        "float-slow": {
          "0%, 100%": { transform: "translate3d(0, 0, 0)" },
          "50%": { transform: "translate3d(0, -18px, 0)" },
        },
        "pulse-flow": {
          "0%, 100%": { opacity: "0.42" },
          "50%": { opacity: "0.88" },
        },
      },
      animation: {
        "float-slow": "float-slow 10s ease-in-out infinite",
        "pulse-flow": "pulse-flow 4.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;

