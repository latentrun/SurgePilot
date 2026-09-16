import { defineComponent, h } from "vue";
import { useData } from "vitepress";
import DefaultTheme from "vitepress/theme";

import MarketingHome from "./MarketingHome.vue";
import "./custom.css";
import "./marketing/marketing.css";

const Layout = defineComponent({
  setup() {
    const { frontmatter } = useData();
    return () =>
      h(
        frontmatter.value.layout === "marketing"
          ? MarketingHome
          : DefaultTheme.Layout,
      );
  },
});

export default {
  extends: DefaultTheme,
  Layout,
};
