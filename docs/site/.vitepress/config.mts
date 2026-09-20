import { writeFileSync } from "node:fs";
import { join } from "node:path";

import { defineConfig, type DefaultTheme } from "vitepress";

import { buildPageHead, transformSeoPageData } from "./seo";
import { PUBLIC_SITE, publicUrl } from "./site";

type NavigationLabels = {
  home: string;
  quickstart: string;
  startupModes: string;
  configuration: string;
  firstRun: string;
  faq: string;
  getStarted: string;
  termsAndFaq: string;
  languageMenu: string;
};

function localeLink(prefix: string, path = "") {
  return `${prefix}${path}`;
}

function localeTheme(prefix: string, labels: NavigationLabels): DefaultTheme.Config {
  return {
    langMenuLabel: labels.languageMenu,
    nav: [
      { text: labels.home, link: localeLink(prefix) },
      { text: labels.quickstart, link: localeLink(prefix, "quickstart") },
      { text: labels.startupModes, link: localeLink(prefix, "startup-modes") },
      { text: labels.configuration, link: localeLink(prefix, "configuration") },
      { text: labels.firstRun, link: localeLink(prefix, "first-run") },
      { text: labels.faq, link: localeLink(prefix, "faq") },
    ],
    sidebar: [
      {
        text: labels.getStarted,
        items: [
          { text: labels.quickstart, link: localeLink(prefix, "quickstart") },
          { text: labels.startupModes, link: localeLink(prefix, "startup-modes") },
          {
            text: labels.configuration,
            link: localeLink(prefix, "configuration"),
          },
          { text: labels.firstRun, link: localeLink(prefix, "first-run") },
          { text: labels.termsAndFaq, link: localeLink(prefix, "faq") },
        ],
      },
    ],
  };
}

const englishLabels: NavigationLabels = {
  home: "Documentation Home",
  quickstart: "Quickstart",
  startupModes: "Startup Modes",
  configuration: "Configuration",
  firstRun: "First Run",
  faq: "FAQ",
  getStarted: "Get Started",
  termsAndFaq: "Terms and FAQ",
  languageMenu: "Change language",
};

const chineseLabels: NavigationLabels = {
  home: "文档首页",
  quickstart: "快速开始",
  startupModes: "启动模式",
  configuration: "配置",
  firstRun: "首次运行",
  faq: "常见问题",
  getStarted: "开始使用",
  termsAndFaq: "术语与常见问题",
  languageMenu: "切换语言",
};

const japaneseLabels: NavigationLabels = {
  home: "ドキュメントホーム",
  quickstart: "クイックスタート",
  startupModes: "起動モード",
  configuration: "設定",
  firstRun: "初回実行",
  faq: "FAQ",
  getStarted: "はじめに",
  termsAndFaq: "用語と FAQ",
  languageMenu: "言語を変更",
};

export default defineConfig({
  base: PUBLIC_SITE.base,
  appearance: "dark",
  cleanUrls: true,
  title: "SurgePilot",
  titleTemplate: false,
  description:
    "A distributed API load-testing platform built by AI agents under explicit engineering governance.",
  head: [
    [
      "link",
      {
        rel: "icon",
        type: "image/svg+xml",
        href: `${PUBLIC_SITE.base}surgepilot-logo.svg`,
      },
    ],
    ["meta", { name: "theme-color", content: "#070a0f" }],
  ],
  transformPageData: transformSeoPageData,
  transformHead: ({ page }) => buildPageHead(page),
  sitemap: {
    hostname: publicUrl(),
  },
  buildEnd: (siteConfig) => {
    writeFileSync(
      join(siteConfig.outDir, "robots.txt"),
      [
        "User-agent: *",
        `Allow: ${PUBLIC_SITE.base}`,
        "",
        `Sitemap: ${publicUrl("/sitemap.xml")}`,
        "",
      ].join("\n"),
      "utf8",
    );
  },
  locales: {
    root: {
      label: "English",
      lang: "en-US",
      link: "/docs/",
      themeConfig: localeTheme("/docs/", englishLabels),
    },
    "docs/zh-CN": {
      label: "简体中文",
      lang: "zh-CN",
      link: "/docs/zh-CN/",
      title: "SurgePilot 用户文档",
      description: "SurgePilot 安装、启动和负载测试用户文档。",
      themeConfig: localeTheme("/docs/zh-CN/", chineseLabels),
    },
    "docs/ja": {
      label: "日本語",
      lang: "ja",
      link: "/docs/ja/",
      title: "SurgePilot ユーザードキュメント",
      description: "SurgePilot のインストール、起動、負荷テストに関するユーザーガイド。",
      themeConfig: localeTheme("/docs/ja/", japaneseLabels),
    },
  },
  themeConfig: {
    logo: "/surgepilot-logo.svg",
    logoLink: PUBLIC_SITE.base,
  },
});
