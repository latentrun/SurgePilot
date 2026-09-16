/** @type {import("tailwindcss").Config} */
export default {
  content: [
    "./.vitepress/theme/MarketingHome.vue",
    "./.vitepress/theme/marketing/marketing-markup.ts",
  ],
  important: ".marketing-landing",
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        primary: "var(--marketing-primary)",
        secondary: "var(--marketing-secondary)",
        "on-surface": "var(--marketing-on-surface)",
        "on-surface-variant": "var(--marketing-on-surface-variant)",
      },
      fontFamily: {
        display: ["SurgePilot Geist", "sans-serif"],
        technical: ["SurgePilot JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
