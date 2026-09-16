<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { withBase } from "vitepress";

import { PUBLIC_SITE } from "../site";
import { getPublicMarketingMarkup } from "./marketing/marketing-markup";

const root = ref<HTMLElement | null>(null);
const markup = getPublicMarketingMarkup({
  logo: withBase("/surgepilot-logo.svg"),
  docs: withBase("/docs/"),
  quickstart: withBase("/docs/quickstart"),
  configuration: withBase("/docs/configuration"),
  repository: PUBLIC_SITE.repository,
  releases: PUBLIC_SITE.releases,
});

let revealObserver: IntersectionObserver | null = null;
let counterInterval: number | null = null;

function parseCounterValue(target: HTMLElement) {
  const currentText = target.innerText ?? target.textContent ?? "0";
  return Number.parseInt(currentText.replace(/,/g, ""), 10) || 0;
}

function writeCounterValue(target: HTMLElement, value: number) {
  const formattedValue = value.toLocaleString();
  target.innerText = formattedValue;
  target.textContent = formattedValue;
}

onMounted(() => {
  const landing = root.value;
  if (!landing) {
    return;
  }

  const reveals = Array.from(
    landing.querySelectorAll<HTMLElement>(".reveal-on-scroll"),
  );
  reveals.forEach((element) => element.classList.add("active"));

  const targetCounters = Array.from(
    landing.querySelectorAll<HTMLElement>(".counter[data-target]"),
  );
  const fastCounters = Array.from(
    landing.querySelectorAll<HTMLElement>(".counter-fast"),
  );
  const nextIncrement = (index: number, tick: number) =>
    ((index + tick * 3) % 9) + 1;
  let tick = 0;
  let targetCountersComplete = targetCounters.length === 0;
  counterInterval = window.setInterval(() => {
    tick += 1;
    if (!targetCountersComplete) {
      targetCountersComplete = targetCounters.every((counter) => {
        const targetValue =
          Number.parseInt(counter.dataset.target ?? "0", 10) || 0;
        const progress = Math.min(tick / 20, 1);
        const nextValue = Math.round(targetValue * progress);
        writeCounterValue(counter, nextValue);
        return nextValue >= targetValue;
      });
    }
    fastCounters.forEach((counter, index) => {
      writeCounterValue(
        counter,
        parseCounterValue(counter) + nextIncrement(index, tick),
      );
    });
  }, 100);

  if (!("IntersectionObserver" in window)) {
    return;
  }

  revealObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("active");
          revealObserver?.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.1 },
  );
  reveals.forEach((element) => revealObserver?.observe(element));
});

onBeforeUnmount(() => {
  revealObserver?.disconnect();
  if (counterInterval !== null) {
    window.clearInterval(counterInterval);
  }
});
</script>

<template>
  <a class="marketing-skip" href="#main-content">Skip to content</a>
  <main
    id="main-content"
    ref="root"
    class="marketing-landing static-dot-grid relative"
    data-marketing-home
    v-html="markup"
  ></main>
</template>
