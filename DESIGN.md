# Design Direction - "Night Signal"

Locked identity for the React rebuild (web/ui). Third direction chosen after
seeing a live reference (21st.dev / cult-ui's "Polar Subscription" template,
https://21st.dev/community/templates/polar-subscription) and asking for a full
reskin toward its dark, neon, bold-hero energy. Supersedes "Study Hall" and the
earlier "Berry Bright" entirely.

Product name: **VYBE Learn**. Chosen after the neon direction, and echoes the
"Vibe Marketing" copy voice of the reference template on purpose.

Two of the original 30 anti-slop constraints (no neon colors, no radial glow
orbs) are intentionally overridden by this direction, per explicit request.
Every other constraint from that list still applies in full, including no
fake testimonials - a caption on the onboarding hero panel is an honest,
unattributed line about the product, never a quote put in a fabricated
person's mouth.

## Product

A Duolingo-style gamified educator, not a dashboard. A learner brings a messy
spreadsheet; the agent fixes what is broken, checks the result actually works,
fits a model that suits it, and turns every decision into a short lesson with
an analogy and a "guess before the reveal" moment.

## What was borrowed from the reference, and what was not

Borrowed: dark background, a single vivid neon accent used with intent (not a
rainbow), an oversized confident hero headline, a glowing primary CTA, a bold
asymmetric two-panel hero layout.

Deliberately NOT copied: the reference's own stock photo, its copy ("Vibe
Marketing"), its fabricated testimonial wall (the same six names repeated on
loop), its "Most Popular" 3-tier pricing block, and its generic AI-SaaS FAQ.
Those are either specific to that product, copyrighted imagery, or patterns
antislop bans outright regardless of color direction (fake social proof, a
"Most Popular" pricing tier). Our hero's right panel is an original abstract
visual built from the product's own data (a scatter/point-cloud motif), not a
photo.

## Palette - "Night Signal"

| Role | Token | Hex |
|---|---|---|
| Background (near-black, not pure) | `--bg` | `#0B0A10` |
| Surface / cards | `--surface` | `#16141C` |
| Ink / primary text (near-white, not pure) | `--ink` | `#F4F2F7` |
| Ink-soft / secondary text | `--ink-soft` | `#948FA0` |
| Hero / primary accent (electric magenta) | `--hero` | `#FF3EA5` |
| Hero pressed | `--hero-deep` | `#D91C82` |
| Pass / kept | `--pass` | `#3DDC8A` |
| Discard / fail | `--fail` | `#FF5C5C` |
| Accent / points | `--points` | `#FFC93C` |
| Hairline / borders | `--line` | `#28242F` |

One neon accent (`--hero`, magenta) does the work a whole gradient would in a
generic template - it is not paired with a second competing neon (no
blue-to-purple, no rainbow). Pass/fail/points are separate, desaturated-enough
functional colors so they never compete with the hero accent.

## Typography

- Display / headings: **Sora**, 600-800. Chunky, geometric, holds up at very
  large sizes the way the reference's oversized hero type does.
- Body: **Plus Jakarta Sans**, 400-700.
- Loaded via Google Fonts `<link>` in `web/ui/index.html`.
- Banned per anti-slop: Inter, Geist, Space Grotesk, Fraunces. (Also not
  reusing Newsreader/Hanken Grotesk or Bricolage/Manrope from the two
  superseded directions, to keep this system visually distinct.)

## Shape, depth, motion

- Radius: `--radius-app: 12px` on cards and buttons - rounder than Study
  Hall, sharper than a full pill, matching the reference's button shape.
- Glow is reserved for the primary CTA only (antislop R-13: 1-2 elements
  max) - a soft magenta shadow that intensifies on hover/press. Cards and
  secondary buttons stay flat with a hairline border, no glow, no blur.
- One accent color, used at the moments that matter (the hero panel, the
  primary CTA, active states) - not smeared across every icon and border.
- Motion: hero elements enter with a slightly more energetic fade + rise than
  Study Hall's calm fade (`y: 10px`, `0.5s`, slight spring), plus the same
  scroll-reveal and self-animating down-hint components already built.

## Copy voice

Unchanged from prior directions: short, plain, warm, second person, no
emojis, no em dashes, no "it's not x, it's y", no checkmark-bullet marketing
lists, no fake testimonials, no fabricated pricing tiers (the product has
neither testimonials nor pricing to show, so none are invented).

## The one mechanic that cannot change

Predict-then-reveal. The learner guesses which strategy will pass, or whether
the first fix will hold, before the agent runs. The agent's decision is
deterministic and computed independently, server-side. The guess is scored but
never changes what the agent actually did or what the pipeline outputs.

## Build

React + Vite + Tailwind v4 + shadcn conventions, in `web/ui/`. FastAPI layer
(`web/api.py`, `web/pipeline.py`, `web/copy.py`) is unchanged and
stack-agnostic; `web/ui` proxies `/api` to it in dev and the built `dist/` is
served by it in prod.
