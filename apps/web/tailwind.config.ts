import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0b0c0d",
        bone: "#fafaf7",
        paper: "#ffffff",
        line: "#e5e5e2",
        muted: "#6b6b6b",
        accent: {
          DEFAULT: "#5b5bd6",
          soft: "#eef0ff",
          dark: "#3f3fa6",
        },
        status: {
          pass: "#1f7a4d",
          caution: "#a06a00",
          fail: "#a32020",
          go: "#1f7a4d",
          conditional: "#a06a00",
          nogo: "#a32020",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "-apple-system",
          "BlinkMacSystemFont",
          "Inter",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 0 rgba(0,0,0,0.02), 0 1px 3px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
