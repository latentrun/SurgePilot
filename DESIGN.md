---
name: Cyber Tech Command
colors:
  surface: '#0a0e1a'
  surface-dim: '#0a0e1a'
  surface-bright: '#353946'
  surface-container-lowest: '#0a0e1a'
  surface-container-low: '#171b28'
  surface-container: '#1b1f2c'
  surface-container-high: '#262a37'
  surface-container-highest: '#313442'
  on-surface: '#dfe2f3'
  on-surface-variant: '#bbc9cd'
  inverse-surface: '#dfe2f3'
  inverse-on-surface: '#2c303d'
  outline: '#94a3b8'
  outline-variant: '#3c494c'
  surface-tint: '#2fd9f4'
  primary: '#8aebff'
  on-primary: '#00363e'
  primary-container: '#22d3ee'
  on-primary-container: '#005763'
  inverse-primary: '#006877'
  secondary: '#d3bbff'
  on-secondary: '#3f008d'
  secondary-container: '#5d03ca'
  on-secondary-container: '#c7aaff'
  tertiary: '#ffd0e0'
  on-tertiary: '#640039'
  tertiary-container: '#ffa7c9'
  on-tertiary-container: '#9b005c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#a2eeff'
  primary-fixed-dim: '#2fd9f4'
  on-primary-fixed: '#001f25'
  on-primary-fixed-variant: '#004e5a'
  secondary-fixed: '#ebddff'
  secondary-fixed-dim: '#d3bbff'
  on-secondary-fixed: '#250059'
  on-secondary-fixed-variant: '#5b00c5'
  tertiary-fixed: '#ffd9e4'
  tertiary-fixed-dim: '#ffb0cd'
  on-tertiary-fixed: '#3e0022'
  on-tertiary-fixed-variant: '#8c0053'
  background: '#0a0e1a'
  on-background: '#dfe2f3'
  surface-variant: '#313442'
  aurora-purple: '#6d28d9'
  aurora-cyan: '#06b6d4'
  aurora-magenta: '#ec4899'
typography:
  display-lg:
    fontFamily: 'Geist'
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: '-0.02em'
  headline-lg:
    fontFamily: 'Geist'
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: '-0.01em'
  headline-md:
    fontFamily: 'Geist'
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: 'Geist'
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: 'Geist'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  technical-lg:
    fontFamily: 'JetBrains Mono'
    fontSize: 20px
    fontWeight: '500'
    lineHeight: '1.4'
  technical-md:
    fontFamily: 'JetBrains Mono'
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: '0.02em'
  label-sm:
    fontFamily: 'JetBrains Mono'
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-padding: 24px
  gutter: 16px
  section-gap: 48px
---

## Brand & Style
The design system embodies the precision and authority of a high-stakes mission control center. It is built for a performance load testing platform where reliability, speed, and technical depth are paramount. The aesthetic is "Dark Glassmorphism"—a sophisticated blend of deep-space aesthetics and futuristic functionalism.

The UI should evoke a sense of "calm under pressure." It uses expansive dark surfaces to reduce eye strain during long monitoring sessions, punctuated by vibrant, neon data points that draw immediate attention to critical metrics. Every element feels like a high-tech instrument: light, translucent, yet structurally sound.

**Key Stylistic Pillars:**
- **Atmospheric Depth:** Multi-layered translucency mimics high-end aerospace interfaces.
- **Precision Engineering:** Monospaced data points and sharp contrast reflect technical accuracy.
- **Futuristic Vibrancy:** Aurora-inspired glows represent the "energy" of live traffic and data flow.

## Colors
The palette is rooted in a "Deep Space Navy" base, providing a high-contrast environment for luminous accents.

- **The Void (Base):** `#0a0e1a` serves as the primary canvas (mapped to `surface` and `background`). It should be applied to the lowest z-index surfaces.
- **Aurora Accents:** Use Purple (`#6d28d9` / `aurora-purple`), Cyan (`#06b6d4` / `aurora-cyan`), and Magenta (`#ec4899` / `aurora-magenta`) sparingly as background radial gradients (15-20% opacity) to create atmospheric depth.
- **Action & State:** Electric Cyan is the primary driver for interaction. Success, Warning, and Danger colors use highly saturated "Neon" variants to ensure they pop against the dark glass surfaces.
- **Grays/Neutrals:** Use Slate-400 (`#94a3b8`, mapped to `outline`) for secondary text and borders to maintain a hierarchy that favors the pure white primary data.

## Typography
The typography strategy differentiates between "Narrative" content and "Data" content.

- **Primary Interface (Geist):** Use Geist for all headings, navigational elements, and body descriptions. Its modern, geometric sans-serif construction provides a clean, professional "SaaS" feel.
- **Data & Metrics (JetBrains Mono):** All numerical values, KPIs, logs, and technical strings must use JetBrains Mono. This monospaced typeface ensures that fluctuating numbers in dashboards don't cause layout shift and reinforces the developer-centric nature of the platform.
- **Hierarchy:** Use heavy weights (600+) for headlines to ground the translucent UI. Labels and small metadata should always be monospaced to feel like "code."

## Layout & Spacing
This design system utilizes a **12-column fluid grid** for dashboard views and a **fixed-center grid** (max-width 1440px) for settings and documentation pages.

- **Grid Logic:** A strictly enforced 8px base unit ensures mathematical alignment.
- **Dashboards:** Use a "Modular Tile" approach. Components should snap to the grid with 16px gutters.
- **Safe Areas:** Maintain a 24px margin on mobile and 48px on desktop to allow the background "Aurora" gradients to breathe.
- **Density:** Provide high-density views for data logs (using the `technical-md` type) and low-density views for high-level executive summaries.

## Elevation & Depth
Depth is achieved through the physical properties of glass rather than traditional shadows.

- **Glass Layers:** Use `rgba(255, 255, 255, 0.05)` for the card surface. Apply a `backdrop-blur` of `12px`.
- **Border Treatment:** Every card must have a 1px solid border of `rgba(255, 255, 255, 0.1)`. This "specular highlight" defines the shape against the dark background.
- **Glow Effects:** Instead of drop shadows, use "Outer Glows." Active elements or high-priority cards should have a soft `0px 0px 20px` shadow colored with the primary Cyan at 30% opacity.
- **Holographic Edges:** For Hero components or primary CTAs, use a subtle linear-gradient border (Cyan to Magenta) at 1px width to suggest a "holographic" projection.

## Shapes
The shape language is modern and approachable but retains a structural, engineered feel.

- **Cards & Containers:** Use a 16px (`rounded-lg`) radius to soften the high-tech aesthetic and make the glass panels feel like premium hardware.
- **Interactive Elements:** Buttons and Input fields should follow an 8px radius for a sharper, more tactical look compared to the larger containers.
- **Status Indicators:** Chips and status dots should be fully pill-shaped (rounded-full) to distinguish them from structural UI components.

## Components
Consistent application of the glassmorphism style across all interactive elements.

- **Buttons:**
    - *Primary:* Electric Cyan background, black text (for legibility), and a cyan outer glow.
    - *Secondary:* Ghost style with the 1px white/0.1 border and `backdrop-blur`.
- **Input Fields:** Semi-transparent dark fills (`rgba(0,0,0,0.2)`) with a bottom-accent border that glows Cyan on focus. Use monospaced font for input text.
- **Data Cards:** The "Command Center" staple. Must include a `12px` backdrop blur, a 1px subtle border, and a technical label in the top-left corner using `label-sm`.
- **KPI Widgets:** Features a large JetBrains Mono value. If the metric is "Healthy," use a subtle Neon Green glow behind the text.
- **Progress Bars:** Use a "segmented" look (vertical dividers every 10%) to look like a hardware frequency monitor.
- **Lists:** Rows should be separated by thin `rgba(255,255,255,0.05)` lines. Hover states should trigger a slight brightening of the background glass to `rgba(255,255,255,0.08)`.
