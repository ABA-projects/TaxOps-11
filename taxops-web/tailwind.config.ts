import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Sistema de diseño (mismo que la landing): neutros de papel columnar, acento verde.
      // Los nombres brand.orange / brand.navy se conservan para no tocar ~120 usos en páginas;
      // el valor es el nuevo. Renombrarlos es una limpieza aparte.
      colors: {
        brand: {
          orange: "#146b53",
          "orange-light": "#1f8a6c",
          navy: "#17201c",
          "navy-dark": "#101614",
          "navy-light": "#4fbf9a",
        },
        // gray = neutros claros con tinte verde-papel; slate = neutros del modo oscuro.
        gray: {
          50: "#f4f6f1", 100: "#eaeee7", 200: "#d8ded8", 300: "#c3cdc7", 400: "#8f9c96",
          500: "#5f6b66", 600: "#4a5550", 700: "#333d38", 800: "#232c27", 900: "#17201c", 950: "#101614",
        },
        slate: {
          50: "#f4f6f1", 100: "#e8ede9", 200: "#dfe5e0", 300: "#c3cdc7", 400: "#9aa8a1",
          500: "#5f6b66", 600: "#3a463f", 700: "#2a342e", 800: "#182019", 900: "#101614", 950: "#0b100e",
        },
      },
      fontFamily: {
        sans: ["var(--font-body)", "Segoe UI", "sans-serif"],
        serif: ["var(--font-display)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
