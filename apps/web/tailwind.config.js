/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--color-background)",
        "border-subtle": "var(--color-border-subtle)",
        error: "var(--color-error)",
        "error-container": "var(--color-error-container)",
        "on-error-container": "var(--color-on-error-container)",
        "on-primary": "var(--color-on-primary)",
        primary: "var(--color-primary)",
        "primary-container": "var(--color-primary-container)",
        secondary: "var(--color-secondary)",
        success: "var(--color-success)",
        "surface-container": "var(--color-surface-container)",
        "surface-container-low": "var(--color-surface-container-low)",
        "text-main": "var(--color-text-main)",
        "text-muted": "var(--color-text-muted)",
        warning: "var(--color-warning)",
        "aurora-cyan": "var(--color-aurora-cyan)",
        "aurora-magenta": "var(--color-aurora-magenta)",
        "aurora-purple": "var(--color-aurora-purple)",
      },
      fontFamily: {
        display: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      maxWidth: {
        "container-max": "1280px",
      },
    },
  },
  plugins: [],
};
