import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1D1D2C",
        accent: "#FF6B35",
        gold: "#FFD166",
      },
    },
  },
  plugins: [],
};
export default config;
