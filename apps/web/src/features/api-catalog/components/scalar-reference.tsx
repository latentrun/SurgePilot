import {
  Component,
  type ErrorInfo,
  type ReactNode,
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { ApiReferenceReact } from "@scalar/api-reference-react";
import type { AnyApiReferenceConfiguration } from "@scalar/api-reference-react";
import scalarStyles from "@scalar/api-reference-react/style.css?inline";

type ScalarColorMode = "light-mode" | "dark-mode";

const defaultScalarColorMode: ScalarColorMode = "dark-mode";
const scalarTeleportStyleAttribute = "data-surgepilot-scalar-teleport-styles";
const scalarColorModeClasses: ScalarColorMode[] = ["light-mode", "dark-mode"];
const scalarSidebarNavigationTimeoutMs = 3_000;
const scalarSidebarNavigationRetryMs = 50;
const fallbackScalarRootVariables = `
  --scalar-border-width: .5px;
  --scalar-radius: 3px;
  --scalar-radius-lg: 6px;
  --scalar-radius-xl: 8px;
  --scalar-font: "Inter", ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
  --scalar-font-code: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
`;

export function apiCatalogScalarConfiguration(
  contentUrl: string,
  onSidebarClick?: (href: string) => void,
): AnyApiReferenceConfiguration {
  return {
    url: contentUrl,
    layout: "modern",
    hideTestRequestButton: true,
    hideClientButton: true,
    documentDownloadType: "none",
    darkMode: true,
    hideDarkModeToggle: false,
    persistAuth: false,
    telemetry: false,
    showDeveloperTools: "never",
    agent: { disabled: true, hideAddApi: true },
    mcp: { disabled: true },
    onSidebarClick,
  };
}

export function apiCatalogScalarHashCandidates(hash: string) {
  const rawFragment = hash.startsWith("#") ? hash.slice(1) : hash;
  if (!rawFragment) return [];

  let decodedFragment = rawFragment;
  try {
    decodedFragment = decodeURIComponent(rawFragment);
  } catch {
    decodedFragment = rawFragment;
  }

  const normalizedFragment = decodedFragment.replace(/^\/+/, "");
  const scalarPrefixedFragment = normalizedFragment.startsWith("api-1/")
    ? normalizedFragment
    : `api-1/${normalizedFragment}`;

  return Array.from(
    new Set([rawFragment, decodedFragment, normalizedFragment, scalarPrefixedFragment]),
  ).filter(Boolean);
}

export function apiCatalogScalarHashIsTagOnly(hash: string) {
  const rawFragment = (hash.startsWith("#") ? hash.slice(1) : hash).replace(/^\/+/, "");
  const normalizedFragment = rawFragment.startsWith("api-1/")
    ? rawFragment.slice("api-1/".length)
    : rawFragment;
  const segments = normalizedFragment.split("/").filter(Boolean);

  return segments.length === 2 && segments[0] === "tag";
}

function escapeCssIdentifier(value: string) {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/g, "\\$&");
}

function findScalarHashTarget(shadowRoot: ShadowRoot, hash: string) {
  for (const candidate of apiCatalogScalarHashCandidates(hash)) {
    const byId = shadowRoot.getElementById(candidate);
    if (byId) return byId;

    const escapedCandidate = escapeCssIdentifier(candidate);
    const bySelector = shadowRoot.querySelector<HTMLElement>(
      `[id="${escapedCandidate}"], [data-id="${escapedCandidate}"]`,
    );
    if (bySelector) return bySelector;
  }

  return null;
}

function sanitizeScalarTeleportStyles(styles: string) {
  const scalarScopedStart = styles.indexOf(":where(.scalar-app)");
  if (scalarScopedStart === -1) return "";

  const themeStart = styles.indexOf(".dark-mode");
  const themedPrefix =
    themeStart >= 0 && themeStart < scalarScopedStart
      ? styles.slice(themeStart, scalarScopedStart)
      : "";

  return `${themedPrefix}\n${styles.slice(scalarScopedStart)}`
    .replace(/(^|})\s*body\s*\{[^}]*\}/g, "$1")
    .trim();
}

function extractScalarRootVariables(styles: string) {
  return styles.match(/:root\s*\{([^{}]*)\}/)?.[1]?.trim() ?? fallbackScalarRootVariables;
}

const scalarRootVariables = extractScalarRootVariables(scalarStyles);

export const apiCatalogScalarRootStyles = `
:host,
.surgepilot-scalar-root {
${scalarRootVariables}
}
`.trim();

export const apiCatalogScalarTeleportStyles = `
.scalar-app {
${scalarRootVariables}
}
${sanitizeScalarTeleportStyles(scalarStyles)}
`.trim();

function scalarBodyApps() {
  return Array.from(document.body.children).filter(
    (node): node is HTMLElement =>
      node instanceof HTMLElement && node.classList.contains("scalar-app"),
  );
}

function readBodyScalarMode(body: HTMLElement): ScalarColorMode | null {
  if (body.classList.contains("dark-mode")) return "dark-mode";
  if (body.classList.contains("light-mode")) return "light-mode";
  return null;
}

function restoreBodyAttribute(
  body: HTMLElement,
  name: "class" | "style",
  initialValue: string | null,
) {
  if (initialValue === null) {
    body.removeAttribute(name);
  } else {
    body.setAttribute(name, initialValue);
  }
}

function useScalarTeleportStyles() {
  useEffect(() => {
    let styleElement = document.head.querySelector<HTMLStyleElement>(
      `style[${scalarTeleportStyleAttribute}]`,
    );
    if (!styleElement) {
      styleElement = document.createElement("style");
      styleElement.setAttribute(scalarTeleportStyleAttribute, "1");
      styleElement.textContent = apiCatalogScalarTeleportStyles;
      document.head.append(styleElement);
    }

    const mountCount = Number(styleElement.dataset.mountCount ?? "0") + 1;
    styleElement.dataset.mountCount = String(mountCount);

    return () => {
      const nextMountCount = Number(styleElement?.dataset.mountCount ?? "1") - 1;
      if (styleElement) {
        if (nextMountCount <= 0) {
          styleElement.remove();
        } else {
          styleElement.dataset.mountCount = String(nextMountCount);
        }
      }
      document.querySelectorAll(".scalar-tooltip").forEach((node) => node.remove());
      scalarBodyApps().forEach((node) => node.remove());
    };
  }, []);
}

function useScalarHostBoundary(wrapperRef: RefObject<HTMLDivElement | null>) {
  useScalarTeleportStyles();

  useEffect(() => {
    const body = document.body;
    const initialClassName = body.className;
    const initialStyle = body.getAttribute("style");
    let activeScalarMode: ScalarColorMode = defaultScalarColorMode;
    let restoring = false;

    function bodyChanged() {
      return body.className !== initialClassName || body.getAttribute("style") !== initialStyle;
    }

    function syncScalarMode(mode = activeScalarMode) {
      activeScalarMode = mode;
      const wrapper = wrapperRef.current;
      if (wrapper) {
        wrapper.classList.remove(...scalarColorModeClasses);
        wrapper.classList.add(mode);
      }

      scalarBodyApps().forEach((node) => {
        node.classList.remove(...scalarColorModeClasses);
        node.classList.add(mode);
      });
    }

    function restore() {
      if (!bodyChanged()) return;
      const scalarMode = readBodyScalarMode(body);
      if (scalarMode) syncScalarMode(scalarMode);

      restoring = true;
      if (body.className !== initialClassName) {
        restoreBodyAttribute(body, "class", initialClassName);
      }
      if (body.getAttribute("style") !== initialStyle) {
        restoreBodyAttribute(body, "style", initialStyle);
      }
      restoring = false;
    }

    const observer = new MutationObserver(() => {
      if (restoring) return;
      syncScalarMode();
      if (bodyChanged()) restore();
    });
    observer.observe(body, {
      attributeFilter: ["class", "style"],
      attributes: true,
      childList: true,
    });
    syncScalarMode();

    return () => {
      observer.disconnect();
      restore();
    };
  }, [wrapperRef]);
}

function useScalarSidebarNavigation(shadowRoot: ShadowRoot | null) {
  const timeoutIds = useRef(new Set<number>());

  const clearPendingAttempts = useCallback(() => {
    timeoutIds.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
    timeoutIds.current.clear();
  }, []);

  useEffect(() => clearPendingAttempts, [clearPendingAttempts]);

  return useCallback(
    (href: string) => {
      if (!shadowRoot) return;
      const activeShadowRoot = shadowRoot;

      clearPendingAttempts();
      const hash = new URL(href, window.location.href).hash;
      if (!hash || apiCatalogScalarHashIsTagOnly(hash)) return;
      const stopTime = Date.now() + scalarSidebarNavigationTimeoutMs;

      function scrollToTarget() {
        const target = findScalarHashTarget(activeShadowRoot, hash);
        if (target) {
          target.scrollIntoView({ block: "start" });
          return;
        }

        if (Date.now() >= stopTime) return;
        const timeoutId = window.setTimeout(() => {
          timeoutIds.current.delete(timeoutId);
          scrollToTarget();
        }, scalarSidebarNavigationRetryMs);
        timeoutIds.current.add(timeoutId);
      }

      scrollToTarget();
    },
    [clearPendingAttempts, shadowRoot],
  );
}

function ScalarShadowRoot({ contentUrl }: { contentUrl: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [shadowRoot, setShadowRoot] = useState<ShadowRoot | null>(null);

  useScalarHostBoundary(wrapperRef);
  const handleSidebarClick = useScalarSidebarNavigation(shadowRoot);

  useEffect(() => {
    if (!hostRef.current || shadowRoot) return;
    const existingShadowRoot = hostRef.current.shadowRoot;
    setShadowRoot(existingShadowRoot ?? hostRef.current.attachShadow({ mode: "open" }));
  }, [shadowRoot]);

  return (
    <div
      aria-label="API Reference"
      className="api-catalog-scalar min-h-[calc(100dvh-4rem)] overflow-hidden bg-black"
      ref={hostRef}
    >
      {shadowRoot
        ? createPortal(
            <div
              className="surgepilot-scalar-root dark-mode min-h-[calc(100dvh-4rem)] bg-black"
              ref={wrapperRef}
            >
              <style>{apiCatalogScalarRootStyles}</style>
              <style>{scalarStyles}</style>
              <ApiReferenceReact
                configuration={apiCatalogScalarConfiguration(contentUrl, handleSidebarClick)}
              />
            </div>,
            shadowRoot,
          )
        : null}
    </div>
  );
}

export function ScalarReference({ contentUrl }: { contentUrl: string }) {
  return <ScalarShadowRoot contentUrl={contentUrl} />;
}

export class ScalarReferenceErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(_error: Error, _errorInfo: ErrorInfo) {
    // Intentionally keep Scalar renderer errors local to API Catalog detail.
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-2xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger">
          API reference rendering is unavailable. Return to API Catalog and try again.
        </div>
      );
    }
    return this.props.children;
  }
}
