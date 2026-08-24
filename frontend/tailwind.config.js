/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: "#0B0F17",
        surface: "#0F131C",
        "surface-container": "#1C2028",
        "surface-container-low": "#181C24",
        "surface-container-high": "#262A33",
        "surface-container-lowest": "#0A0E16",
        "on-surface": "#DFE2EE",
        "on-surface-variant": "#BBCABF",
        primary: "#4EDEA3",
        "primary-container": "#10B981",
        "on-primary": "#003824",
        secondary: "#ADC6FF",
        "secondary-container": "#0566D9",
        tertiary: "#FFB95F",
        "tertiary-container": "#E29100",
        error: "#FFB4AB",
        "error-container": "#93000A",
      },
      fontFamily: {
        display: ["Outfit", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
}
