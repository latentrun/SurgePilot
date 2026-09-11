import {
  Component,
  type ErrorInfo,
  type RefObject,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { ApiReferenceReact } from "@scalar/api-reference-react";
import type { AnyApiReferenceConfiguration } from "@scalar/api-reference-react";
import scalarStyles from "@scalar/api-reference-react/style.css?inline";

const teleportStyleAttribute = "data-surgepilot-scalar-teleport-styles";

export function apiCatalogScalarConfiguration(contentUrl: string): AnyApiReferenceConfiguration {
  const url = new URL(contentUrl, window.location.origin);
  if (url.origin !== window.location.origin) {
    throw new Error("API Catalog content must be same-origin");
  }
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
  };
}

function scalarBodyApps() {
  return Array.from(document.body.children).filter(
    (node): node is HTMLElement => node instanceof HTMLElement && node.classList.contains("scalar-app"),
  );
}

function useScalarBoundary(wrapperRef: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const body = document.body;
    const initialClass = body.className;
    const initialStyle = body.getAttribute("style");
    const style = document.createElement("style");
    style.setAttribute(teleportStyleAttribute, "1");
    style.textContent = `.scalar-app { ${scalarStyles.match(/:root\s*\{([^{}]*)\}/)?.[1] ?? ""} }\n${scalarStyles.replace(/(^|})\s*body\s*\{[^}]*\}/g, "$1")}`;
    document.head.append(style);
    let restoring = false;
    const restore = () => {
      if (body.className === initialClass && body.getAttribute("style") === initialStyle) return;
      restoring = true;
      body.className = initialClass;
      if (initialStyle === null) body.removeAttribute("style");
      else body.setAttribute("style", initialStyle);
      restoring = false;
    };
    const observer = new MutationObserver(() => {
      if (restoring) return;
      wrapperRef.current?.classList.add("dark-mode");
      scalarBodyApps().forEach((node) => node.classList.add("dark-mode"));
      if (body.className !== initialClass || body.getAttribute("style") !== initialStyle) restore();
    });
    observer.observe(body, { attributes: true, attributeFilter: ["class", "style"], childList: true });
    return () => {
      observer.disconnect();
      restore();
      style.remove();
      document.querySelectorAll(".scalar-tooltip").forEach((node) => node.remove());
      scalarBodyApps().forEach((node) => node.remove());
    };
  }, [wrapperRef]);
}

function ScalarShadowRoot({ contentUrl }: { contentUrl: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [shadowRoot, setShadowRoot] = useState<ShadowRoot | null>(null);
  useScalarBoundary(wrapperRef);

  useEffect(() => {
    if (!hostRef.current || shadowRoot) return;
    setShadowRoot(hostRef.current.shadowRoot ?? hostRef.current.attachShadow({ mode: "open" }));
  }, [shadowRoot]);

  return (
    <div aria-label="API Reference" className="api-catalog-scalar min-h-[calc(100dvh-4rem)] overflow-hidden bg-black" ref={hostRef}>
      {shadowRoot ? createPortal(
        <div className="surgepilot-scalar-root dark-mode min-h-[calc(100dvh-4rem)] bg-black" ref={wrapperRef}>
          <style>{scalarStyles}</style>
          <ApiReferenceReact configuration={apiCatalogScalarConfiguration(contentUrl)} />
        </div>,
        shadowRoot,
      ) : null}
    </div>
  );
}

export function ScalarReference({ contentUrl }: { contentUrl: string }) {
  return <ScalarShadowRoot contentUrl={contentUrl} />;
}

export class ScalarReferenceErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) {}
  render() {
    return this.state.hasError
      ? <div className="rounded-2xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger">API reference rendering is unavailable. Return to API Catalog and try again.</div>
      : this.props.children;
  }
}
