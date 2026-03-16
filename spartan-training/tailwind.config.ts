import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        spartan: { gold: "#d4a843", dark: "#0c0f13", card: "#141820", border: "#2a3348" },
      },
      fontFamily: { sans: ['"DM Sans"', "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
