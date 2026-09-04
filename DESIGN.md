---
name: Cyber Tech Command
colors:
  surface: '#0a0e1a'
  surface-container: '#1b1f2c'
  surface-container-high: '#262a37'
  on-surface: '#dfe2f3'
  on-surface-variant: '#bbc9cd'
  outline: '#94a3b8'
  outline-variant: '#3c494c'
  primary: '#8aebff'
  on-primary: '#00363e'
  secondary: '#d3bbff'
  error: '#ffb4ab'
  aurora-purple: '#6d28d9'
  aurora-cyan: '#06b6d4'
  aurora-magenta: '#ec4899'
typography:
  heading:
    fontFamily: 'Geist'
    fontWeight: '600'
  body:
    fontFamily: 'Geist'
    fontWeight: '400'
  technical:
    fontFamily: 'JetBrains Mono'
    fontWeight: '500'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  lg: 1rem
  full: 9999px
spacing:
  base: 8px
  container-padding: 24px
  gutter: 16px
---

# SurgePilot Design Baseline

SurgePilot should feel like a calm, precise command center for performance testing. Dark surfaces reduce visual fatigue during long runs; bright accents draw attention to actions, changing metrics, warnings, and failures.

## Visual principles

- Use deep navy surfaces with restrained cyan, purple, and magenta accents.
- Use Geist for interface copy and JetBrains Mono for metrics, logs, identifiers, and technical values.
- Build layouts on an 8px spacing unit. Dashboard cards use a fluid grid with 16px gutters.
- Prefer subtle translucent surfaces, one-pixel borders, and limited glow over heavy shadows.
- Keep dense operational data readable; do not sacrifice contrast or focus visibility for atmosphere.
- Use color together with text or icons for state. Never make color the only status signal.

## Component baseline

- Primary actions use cyan with dark text; secondary actions use a bordered dark surface.
- Inputs have explicit labels, visible focus treatment, inline validation, and monospaced values where technical.
- Data cards show a concise label, a clear value, and any state or time context needed to interpret it.
- Tables and lists provide loading, empty, error, and disabled states; rows are separated by subtle borders.
- Run status, validity, and SLA verdict are distinct concepts and must never be collapsed into one badge.
- Motion should explain a state change, remain brief, and respect reduced-motion preferences.

## Accessibility baseline

All interactive controls must be keyboard reachable and have accessible names. Text and state indicators must meet practical contrast requirements on the dark palette. Focus order follows reading order, destructive actions require clear wording, and live execution updates must not steal focus.
