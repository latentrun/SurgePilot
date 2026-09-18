# Local Marketing Fonts

These files vendor the Stitch reference fonts for the ADR-0013 static Marketing Landing route so runtime Web pages do not request Google Fonts.

- Geist: Vercel's `geist-font` project, SIL Open Font License 1.1. The exact
  upstream copyright and license text is vendored at [`geist/OFL.txt`](geist/OFL.txt).
- JetBrains Mono: JetBrains' `JetBrainsMono` project, SIL Open Font License 1.1. The
  exact upstream copyright and license text is vendored at
  [`jetbrains-mono/OFL.txt`](jetbrains-mono/OFL.txt).

The font files are used only through the scoped `features/marketing/pages/landing.css` `@font-face` rules.
