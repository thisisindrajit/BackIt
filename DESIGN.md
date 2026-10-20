---
name: BackIt
description: Founding-backer campaigns where early customers pre-buy and earn from referrals.
colors:
  primary: "#83a281"
  primary-hover: "#739371"
  primary-deep: "#4f6d4d"
  secondary: "#c7d3c0"
  accent: "#fff9d6"
  background: "#ffffff"
  foreground: "#1b231c"
  muted: "#f3f5f1"
  muted-foreground: "#5b665a"
  border: "#e6eae3"
  sidebar: "#f5f7f3"
typography:
  display: "Timeless Serif (TimelessSerifVF, STYL 0 Display), italic accents from TimelessSerifItalicVF"
  heading: "Timeless Serif (STYL 100 Text)"
  body: "Timeless Sans (TimelessSansVF, STYL 100)"
radius:
  base: "0.75rem"
  card: "1rem to 1.5rem"
  panel: "2rem"
  button: "9999px (pill)"
---

# Design System: BackIt

## Overview

**Airy and editorial, with one stamp of delight.** The design takes after Air (air.inc): huge serif headlines with one *italic* accent phrase, lots of white space, pill buttons, soft rounded panels, and a left sidebar in the app. BackIt still handles other people's money, so numbers stay large, exact, and labelled. The fun comes from motion and from the **Founding Seal**, never from decoration.

Anti-references: crypto and "invest now" aesthetics, gradient text, hero-metric dashboards, and countdown or scarcity urgency.

## Colors

- **Primary** `#83a281` (sage) fills CTAs, progress, and active states. Hover is `#739371`.
- **Primary deep** `#4f6d4d` sets italic heading accents and links.
- **Secondary** `#c7d3c0` (lichen) is used for the auth panel, the showcase panels, the seal ring, and tile covers. Panels use it at 40–55% opacity.
- **Accent** `#fff9d6` (cream) is used for the seal centre, "not an investment" notices, and waiting states.
- **Neutrals:** white background, `#f3f5f1` muted panels, `#e6eae3` hairlines, `#1b231c` text.

### Rules

- **CTA text is white.** This is a brand requirement. White on `#83a281` measures about 2.6:1, below WCAG AA. The CTA keeps a medium weight and a faint text-shadow, and hover deepens to `#739371`. If contrast matters more later, use `primary-deep` as the CTA fill.
- **Never put large white text on sage panels.** Use lichen or cream panels with dark text.
- **State is written, not only coloured.** Every badge carries a word.

## Typography

Both families are local copies in `apps/web/src/fonts/`. The `.ttf` files are gitignored because the licence forbids redistribution.

- **Timeless Serif (primary)** sets `h1`, `h2`, and `.font-display` with the Display cut (`STYL 0`), weight 400, and -0.02em tracking. It sets `h3`, `h4`, and `.font-heading` with the Text cut (`STYL 100`). Money and campaign stories also use the serif. `<em>` inside a heading renders italic in primary-deep.
- **Timeless Sans (secondary)** sets interface text, labels, body copy, and tables.
- **Money** uses `.tabular`, which sets tabular and lining figures.

## Shape and depth

- **Radius:** pill buttons, tabs, and chips. Inputs use `rounded-xl`, cards `rounded-2xl`, product tiles and buy panels `rounded-3xl`, large panels `rounded-[2rem]`.
- **Shadows:** `--shadow-soft` for resting surfaces and `--shadow-lift` for hovered tiles and buy or checkout cards. Cards also carry a 7% foreground ring.

## Components

- **Founding Seal** (`components/backit/founding-seal.tsx`). A rotating ring of "FOUNDING BACKER • BACKIT.CLUB" text around a cream centre that shows the badge number in italic serif. It appears on the landing page, the auth panel, the buy panel (as the next badge number), the checkout success screen, overview backings, and the backing card.
- **Logo.** Sage "community growth" mark (`public/logo.png`, transparent) beside the Timeless Serif "Back*It*" wordmark; tilts −6° on hover. `src/app/icon.png` / `apple-icon.png` are the favicons.
- **App shell.** shadcn `Sidebar` (inset variant) holding the wordmark, a "New campaign" CTA, nav, and a user menu.
- **Product tiles.** A tinted cover with a giant italic initial, a status pill, then the name and URL. The final tile is a dashed "Add a product" tile.
- **Tabs.** A pill list with a sliding indicator (Base UI `Tabs.Indicator`).
- **Layout.** Every public section, the header and the footer use the `page-shell` utility (`max-w-6xl`, `px-5`/`sm:px-8`), so their edges line up. Tinted bands sit inside it rather than bleeding wider.
- **Landing.** Word-by-word hero rise, a showcase panel with a sample campaign card, the seal, a scrolling "Recent activity" feed (marked "Sample data"), a "BackIt, in plain words" intro with the three roles, four numbered steps, a builders/backers benefits band, three trust cards, an example-based pricing section, an FAQ accordion, and scroll reveals. The header has a centred nav (How it works, Why BackIt, Pricing; hidden below `md`). Keep landing copy simple: no fee or commission mechanics outside the pricing section.

## Motion

Tokens: `--ease-out` is `cubic-bezier(0.23,1,0.32,1)` and `--ease-in-out` is `cubic-bezier(0.77,0,0.175,1)`.

- **UI:** 150–250ms. Buttons press to `scale(0.97)`. Tiles and rows `lift` (-2px plus shadow) only on hover-capable fine pointers.
- **Entrances:** `.rise` (opacity, 8px translate, blur) and `.stagger` (50ms steps) for page content. `.reveal` and `.reveal-grow` use scroll-driven `view()` timelines where supported.
- **Celebration:** the checkout success seal pops in with a one-time confetti burst in brand colours.
- **Ambient:** the seal spins slowly (40s) and the ledger ticker scrolls and pauses on hover.
- **Reduced motion:** entrances become fades, and spin, ticker, and confetti are turned off.
- Animate only `transform`, `opacity`, `filter`, and `clip-path`. Never use `transition: all` or `scale(0)`.

## Don't

- Gradient text, eyebrow labels, section numbers, thick side borders, or identical card grids.
- Urgency mechanics, or any language suggesting investment returns.
