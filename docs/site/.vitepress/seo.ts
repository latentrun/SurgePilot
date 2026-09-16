import type { HeadConfig, PageData } from "vitepress";

import { PUBLIC_SITE, publicUrl } from "./site";

type PageKind = "marketing" | "docs";
type Locale = "en" | "zh-CN" | "ja";

type SeoEntry = {
  source: string;
  route: string;
  slug: string | null;
  lang: Locale;
  kind: PageKind;
  title: string;
  description: string;
};

type LocalizedCopy = {
  title: string;
  description: string;
};

const documentationCopy: Record<Locale, Record<string, LocalizedCopy>> = {
  en: {
    index: {
      title: "SurgePilot Documentation: Install, Configure, and Run",
      description:
        "Install SurgePilot, choose a startup mode, configure the self-hosted stack, and complete a first distributed API load test.",
    },
    quickstart: {
      title: "SurgePilot Quickstart: Start the Self-Hosted Full Stack",
      description:
        "Use the supported SurgePilot installer or source startup path, review first-run configuration, and open the self-hosted control plane.",
    },
    "startup-modes": {
      title: "SurgePilot Startup Modes: Release, Source, and Preview",
      description:
        "Compare SurgePilot tagged-release, complete source, and control-plane preview startup modes and understand their Runtime guarantees.",
    },
    configuration: {
      title: "SurgePilot Configuration Reference for Source and Releases",
      description:
        "Review the authoritative source and tagged-release environment settings for hosts, ports, Runtime assets, Monitoring, and credentials.",
    },
    "first-run": {
      title: "Your First SurgePilot Distributed API Load Test",
      description:
        "Create the first Admin, prepare an environment, Scenario, Test Plan, and Load Node, then run and review a controlled API load test.",
    },
    faq: {
      title: "SurgePilot FAQ: Installation, Load Nodes, Runs, and Safety",
      description:
        "Find precise answers about SurgePilot startup, distributed Load Nodes, Runtime readiness, Run behavior, Monitoring, and safe testing.",
    },
  },
  "zh-CN": {
    index: {
      title: "SurgePilot 中文文档：安装、配置与运行",
      description:
        "安装 SurgePilot、选择启动模式、配置自托管技术栈，并完成第一次分布式 API 负载测试。",
    },
    quickstart: {
      title: "SurgePilot 快速开始：启动自托管完整技术栈",
      description:
        "使用官方安装或源码启动路径，检查首次配置，并打开 SurgePilot 自托管控制平面。",
    },
    "startup-modes": {
      title: "SurgePilot 启动模式：Release、源码与 Preview",
      description:
        "比较 SurgePilot Release、完整源码和控制平面 Preview 启动模式及其 Runtime 就绪保证。",
    },
    configuration: {
      title: "SurgePilot 配置参考：源码与 Release 环境",
      description:
        "查阅源码和 Release 的主机、端口、Runtime、Monitoring 与凭据环境配置。",
    },
    "first-run": {
      title: "第一次 SurgePilot 分布式 API 负载测试",
      description:
        "创建首位管理员、环境、Scenario、Test Plan 和 Load Node，然后执行并评审受控负载测试。",
    },
    faq: {
      title: "SurgePilot 常见问题：安装、Load Node、Run 与安全",
      description:
        "了解 SurgePilot 启动、分布式 Load Node、Runtime 就绪、Run、Monitoring 与安全测试边界。",
    },
  },
  ja: {
    index: {
      title: "SurgePilot 日本語ドキュメント：導入・設定・実行",
      description:
        "SurgePilot を導入し、起動モードとセルフホスト構成を選び、最初の分散 API 負荷テストを実行します。",
    },
    quickstart: {
      title: "SurgePilot クイックスタート：セルフホスト環境を起動",
      description:
        "公式インストーラーまたはソース起動を使い、初回設定を確認して SurgePilot のコントロールプレーンを開きます。",
    },
    "startup-modes": {
      title: "SurgePilot 起動モード：Release・ソース・Preview",
      description:
        "SurgePilot の Release、完全なソース、コントロールプレーン Preview と Runtime 保証を比較します。",
    },
    configuration: {
      title: "SurgePilot 設定リファレンス：ソースと Release",
      description:
        "ホスト、ポート、Runtime、Monitoring、認証情報に関するソース版と Release 版の環境設定を確認します。",
    },
    "first-run": {
      title: "最初の SurgePilot 分散 API 負荷テスト",
      description:
        "最初の管理者、環境、Scenario、Test Plan、Load Node を作成し、制御された負荷テストを実行して確認します。",
    },
    faq: {
      title: "SurgePilot FAQ：導入・Load Node・Run・安全性",
      description:
        "SurgePilot の起動、分散 Load Node、Runtime 準備状態、Run、Monitoring、安全なテスト境界を確認します。",
    },
  },
};

const entries: SeoEntry[] = [
  {
    source: "index.md",
    route: "/",
    slug: null,
    lang: "en",
    kind: "marketing",
    title: "SurgePilot: 100% AI-Built Distributed Load Testing",
    description:
      "Inspect an original AI-authored baseline for self-hosted distributed API load testing, with explicit human/AI responsibilities and repository-backed evidence from requirements through release.",
  },
];

for (const lang of ["en", "zh-CN", "ja"] as const) {
  for (const [slug, copy] of Object.entries(documentationCopy[lang])) {
    const filename = slug === "index" ? "index.md" : `${slug}.md`;
    const localePrefix = lang === "en" ? "" : `${lang}/`;
    const routeSuffix = slug === "index" ? "" : slug;
    entries.push({
      source: `docs/${localePrefix}${filename}`,
      route: `/docs/${localePrefix}${routeSuffix}`,
      slug: slug === "index" ? "" : slug,
      lang,
      kind: "docs",
      title: copy.title,
      description: copy.description,
    });
  }
}

const seoBySource = new Map(entries.map((entry) => [entry.source, entry]));
const socialImage = publicUrl("/surgepilot-architecture.jpg");

function localeRoute(lang: Locale, slug: string) {
  const localePrefix = lang === "en" ? "" : `${lang}/`;
  return `/docs/${localePrefix}${slug}`;
}

function safeJson(value: unknown) {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

function breadcrumb(entry: SeoEntry) {
  const docsHome = seoBySource.get(
    entry.lang === "en" ? "docs/index.md" : `docs/${entry.lang}/index.md`,
  );
  const items = [
    { "@type": "ListItem", position: 1, name: "SurgePilot", item: publicUrl("/") },
    {
      "@type": "ListItem",
      position: 2,
      name: docsHome?.title ?? "Documentation",
      item: publicUrl(localeRoute(entry.lang, "")),
    },
  ];
  if (entry.slug) {
    items.push({
      "@type": "ListItem",
      position: 3,
      name: entry.title,
      item: publicUrl(entry.route),
    });
  }
  return { "@type": "BreadcrumbList", itemListElement: items };
}

function structuredData(entry: SeoEntry) {
  const url = publicUrl(entry.route);
  if (entry.kind === "marketing") {
    return {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebSite",
          name: "SurgePilot",
          url,
          description: entry.description,
          inLanguage: "en",
        },
        {
          "@type": "SoftwareApplication",
          name: "SurgePilot",
          url,
          description: entry.description,
          applicationCategory: "DeveloperApplication",
          operatingSystem: "Self-hosted with Docker; Linux Load Nodes",
          isAccessibleForFree: true,
          codeRepository: PUBLIC_SITE.repository,
          license: `${PUBLIC_SITE.repository}/blob/main/LICENSE`,
        },
      ],
    };
  }
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "TechArticle",
        headline: entry.title,
        description: entry.description,
        url,
        mainEntityOfPage: url,
        inLanguage: entry.lang,
        isPartOf: { "@type": "WebSite", name: "SurgePilot", url: publicUrl("/") },
      },
      breadcrumb(entry),
    ],
  };
}

export function getSeoEntry(source: string) {
  return seoBySource.get(source);
}

export function transformSeoPageData(pageData: PageData) {
  const entry = getSeoEntry(pageData.relativePath);
  if (!entry) return;
  return {
    title: entry.title,
    description: entry.description,
    frontmatter: {
      ...pageData.frontmatter,
      title: entry.title,
      description: entry.description,
      titleTemplate: false,
    },
  };
}

export function buildPageHead(source: string): HeadConfig[] {
  const entry = getSeoEntry(source);
  if (!entry) {
    return [["meta", { name: "robots", content: "noindex,nofollow,noarchive" }]];
  }

  const canonical = publicUrl(entry.route);
  const head: HeadConfig[] = [
    ["link", { rel: "canonical", href: canonical }],
    ["meta", { name: "robots", content: "index,follow,max-image-preview:large" }],
    ["meta", { property: "og:title", content: entry.title }],
    ["meta", { property: "og:description", content: entry.description }],
    ["meta", { property: "og:url", content: canonical }],
    ["meta", { property: "og:type", content: entry.kind === "marketing" ? "website" : "article" }],
    ["meta", { property: "og:image", content: socialImage }],
    ["meta", { property: "og:image:alt", content: "SurgePilot AI-built distributed load-testing system" }],
    ["meta", { property: "og:locale", content: entry.lang === "en" ? "en_US" : entry.lang.replace("-", "_") }],
    ["meta", { name: "twitter:card", content: "summary_large_image" }],
    ["meta", { name: "twitter:title", content: entry.title }],
    ["meta", { name: "twitter:description", content: entry.description }],
    ["meta", { name: "twitter:image", content: socialImage }],
    ["meta", { name: "twitter:image:alt", content: "SurgePilot AI-built distributed load-testing system" }],
    ["script", { type: "application/ld+json" }, safeJson(structuredData(entry))],
  ];

  if (entry.kind === "docs" && entry.slug !== null) {
    for (const lang of ["en", "zh-CN", "ja"] as const) {
      head.push([
        "link",
        {
          rel: "alternate",
          hreflang: lang,
          href: publicUrl(localeRoute(lang, entry.slug)),
        },
      ]);
    }
    head.push([
      "link",
      {
        rel: "alternate",
        hreflang: "x-default",
        href: publicUrl(localeRoute("en", entry.slug)),
      },
    ]);
  }
  return head;
}

export const indexableEntries = Object.freeze(entries);
