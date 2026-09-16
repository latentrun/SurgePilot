import { useEffect, useRef } from "react";
import { Navigate } from "react-router-dom";

import { useAuthSession } from "../../../app/auth-session";
import { LoadingPage } from "../../../app/layouts/loading-page";
import logoUrl from "../../../assets/logo/surgepilot-logo.svg";
import { getStitchLandingMarkup } from "./stitch-landing-markup";
import "./landing.css";

function parseCounterValue(target: HTMLElement) {
  const currentText = target.innerText ?? target.textContent ?? "0";
  return Number.parseInt(currentText.replace(/,/g, ""), 10) || 0;
}

function writeCounterValue(target: HTMLElement, value: number) {
  const formattedValue = value.toLocaleString();
  target.innerText = formattedValue;
  target.textContent = formattedValue;
}

function useStitchLandingEffects(
  rootRef: React.RefObject<HTMLElement | null>,
  enabled: boolean,
  activationKey: string | null,
) {
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const root = rootRef.current;
    if (!root) {
      return undefined;
    }

    const reveals = Array.from(
      root.querySelectorAll<HTMLElement>(".reveal-on-scroll"),
    );
    reveals.forEach((element) => {
      element.classList.add("active");
    });

    const targetCounters = Array.from(
      root.querySelectorAll<HTMLElement>(".counter[data-target]"),
    );
    const fastCounters = Array.from(
      root.querySelectorAll<HTMLElement>(".counter-fast"),
    );
    const nextIncrement = (index: number, tick: number) =>
      ((index + tick * 3) % 9) + 1;
    let tick = 0;
    const counterInterval = window.setInterval(() => {
      tick += 1;
      targetCounters.forEach((counter) => {
        const targetValue =
          Number.parseInt(counter.dataset.target ?? "0", 10) || 0;
        const progress = Math.min(tick / 40, 1);
        writeCounterValue(counter, Math.round(targetValue * progress));
      });
      fastCounters.forEach((counter, index) => {
        writeCounterValue(
          counter,
          parseCounterValue(counter) + nextIncrement(index, tick),
        );
      });
    }, 50);

    const supportsIntersectionObserver = "IntersectionObserver" in window;
    if (!supportsIntersectionObserver) {
      return () => {
        window.clearInterval(counterInterval);
      };
    }

    const revealObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("active");
          }
        }
      },
      { threshold: 0.1 },
    );
    reveals.forEach((element) => revealObserver.observe(element));

    return () => {
      revealObserver.disconnect();
      window.clearInterval(counterInterval);
    };
  }, [activationKey, enabled, rootRef]);
}

export function LandingPage() {
  const {
    clearPostLogoutRedirect,
    isAuthenticated,
    isRestoring,
    postLogoutRedirectPath,
  } = useAuthSession();
  const rootRef = useRef<HTMLElement | null>(null);
  useStitchLandingEffects(
    rootRef,
    !isRestoring && !isAuthenticated,
    // Re-scan the current injected DOM after logout clears its redirect marker.
    postLogoutRedirectPath,
  );

  useEffect(() => {
    if (!isRestoring && !isAuthenticated && postLogoutRedirectPath) {
      clearPostLogoutRedirect();
    }
  }, [
    clearPostLogoutRedirect,
    isAuthenticated,
    isRestoring,
    postLogoutRedirectPath,
  ]);

  if (isRestoring) {
    return <LoadingPage />;
  }
  if (isAuthenticated) {
    return <Navigate to="/overview" replace />;
  }

  return (
    <main
      className="marketing-landing static-dot-grid relative"
      dangerouslySetInnerHTML={{ __html: getStitchLandingMarkup(logoUrl) }}
      ref={rootRef}
    />
  );
}
