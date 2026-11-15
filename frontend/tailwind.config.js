export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 900: "#0b1220", 800: "#111a2e", 700: "#1a2540", 600: "#26345a" },
        accent: { DEFAULT: "#4cc2ff", dim: "#2a7fb0" },
        warn: "#f5b942",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
