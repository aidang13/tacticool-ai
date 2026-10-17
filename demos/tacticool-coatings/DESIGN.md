---
name: Tacti-Cool Coatings
description: The Cerakote sample-chip deck laid out on the shop counter; pick a chip, send the tag.
colors:
  mat: "#1b1c1e"
  mat-2: "#232426"
  mat-tread: "rgba(255,255,255,0.035)"
  ink: "#ebe8e1"
  ink-2: "#b3b0a8"
  ink-3: "#8f8d85"
  rule: "#4a4d50"
  rule-2: "#333538"
  label: "#f5f3ee"
  label-hot: "#ffffff"
  label-ink: "#17181a"
  label-ink-2: "#5e5f5c"
  tag: "#e3cf9e"
  tag-2: "#d4bd87"
  tag-ink: "#2a2416"
  tag-ink-2: "#5c4d2c"
  brass: "#b08d4a"
  brass-2: "#7d6132"
  focus: "#f2c14e"
  err: "#f26b4e"
typography:
  display:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "clamp(2.4rem, 4.1vw, 3.7rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "clamp(2.2rem, 4.6vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    letterSpacing: "0.04em"
  code:
    fontFamily: "Barlow Condensed, system-ui, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "0.02em"
    fontFeature: "tnum"
rounded:
  hairline: "3px"
  strip: "4px"
  slot: "5px"
  chip: "7px"
  panel: "8px"
  tag: "10px 10px 6px 6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "28px"
  section: "80px"
  gutter: "clamp(16px, 4vw, 56px)"
components:
  button-send:
    backgroundColor: "{colors.label-ink}"
    textColor: "{colors.label}"
    rounded: "{rounded.slot}"
    padding: "13px 16px"
  button-send-hover:
    backgroundColor: "#000000"
  button-label:
    backgroundColor: "{colors.label}"
    textColor: "{colors.label-ink}"
    rounded: "{rounded.strip}"
    padding: "9px 14px"
  button-label-hover:
    backgroundColor: "{colors.label-hot}"
  tab:
    backgroundColor: "{colors.mat-2}"
    textColor: "{colors.ink-2}"
    rounded: "7px 7px 0 0"
    padding: "8px 14px 10px"
  tab-active:
    backgroundColor: "{colors.label}"
    textColor: "{colors.label-ink}"
  label-strip:
    backgroundColor: "{colors.label}"
    textColor: "{colors.label-ink}"
    rounded: "{rounded.strip}"
    padding: "8px 12px 9px"
  chip-label:
    backgroundColor: "{colors.label}"
    textColor: "{colors.label-ink}"
    typography: "{typography.code}"
    padding: "5px 7px 6px"
  input-tag:
    backgroundColor: "rgba(255,255,255,0.55)"
    textColor: "{colors.tag-ink}"
    rounded: "{rounded.hairline}"
    padding: "9px 10px"
  input-tag-focus:
    backgroundColor: "{colors.label-hot}"
  slot-button:
    backgroundColor: "rgba(255,255,255,0.4)"
    textColor: "{colors.tag-ink}"
    rounded: "{rounded.slot}"
    padding: "7px"
    height: "62px"
  slot-button-active:
    backgroundColor: "{colors.label-hot}"
  hang-tag:
    backgroundColor: "{colors.tag}"
    textColor: "{colors.tag-ink}"
    rounded: "{rounded.tag}"
    padding: "34px 20px 18px"
  wall:
    backgroundColor: "rgba(0,0,0,0.22)"
    rounded: "0 8px 8px 8px"
    padding: "14px"
---

# Design System: Tacti-Cool Coatings

## Overview

**Creative North Star: "The Color Card"**

The whole page is the Cerakote sample-chip deck laid out on the shop counter. The ground is a charcoal rubber mat with a fine diamond-tread texture; everything that matters sits on it as a physical object: coated aluminum chips with a punched hole and a gloss highlight, white label strips with an H-code and a name, and one manila hang tag with a brass eyelet that is the quote form. The system's own palette is deliberately achromatic and material (mat, label white, manila, brass); chromatic color belongs to the chips, and it only travels off the wall when a visitor picks a chip and it lands on the tag.

The voice is counter-staff: direct, catalog-literal, no hype. Type is a stamped plate, Barlow Condensed set heavy and tight for every heading, label, and code, with Barlow carrying body copy at a comfortable 17px. Density is a counter, not a brochure: chips pack seven or eight to a row, strips sit shoulder to shoulder, and sections are separated by hairline galvanized rules rather than bands of color. There is one motion grammar, an exponential ease-out that lifts a chip and cross-fades the tag's swatch to it; nothing enters, slides, or reveals on scroll.

Confirmed rejections from the chosen world: no gradients as decoration, no icon tiles, no brand accent color beyond what the visitor picks.

**Key Characteristics:**
- Charcoal tread mat as ground; every surface above it is an object that casts a soft two-layer shadow
- Chromatic color lives only in chip faces and picked swatches; chrome is mat, white label, manila, brass
- Barlow Condensed 800 for headings and codes, 700 for labels, Barlow 400/500/600 for body and names
- Label strips are the universal control surface: tabs, buttons, process heads, pairing captions, chip labels
- The quote form is a manila hang tag with a notched top, punched eyelet, brass rim, and string
- One easing, cubic-bezier(.16,1,.3,1), for every lift and cross-fade; no per-section entrances

## Colors

A material palette: a charcoal mat, warm off-white label stock, manila tag stock, and brass hardware, with chromatic color reserved for the Cerakote chips themselves.

### Primary
- **Label White** (`label`): the stock of every label strip. Backgrounds for tabs when pressed, strip buttons (nav CTA, "Add photos", sister-shop link, mobile bar link), process heads in the spec table, item strips, pairing captions, the chip's own label, and the step numerals.
- **Label Ink** (`label-ink`): near-black print on label stock. Text on every strip, the fill of the send button and the mobile bar's link, the slot badge on a picked chip, and the checkbox tick.
- **Label Ink Muted** (`label-ink-2`): secondary print on a strip: the chip's color name, a strip's subline, pairing codes, the dashed border of the empty mobile-bar swatch.
- **Label Hot** (`label-hot`): pure white, used only as a state: label buttons on hover, inputs on focus, a checked checkbox, a pressed slot button, and the message card. It reads as the strip catching light.

### Secondary
- **Manila** (`tag`): the hang tag's stock, used for the quote tag and the find-us mini tag. Nothing else is manila.
- **Manila Edge** (`tag-2`): the default border of inputs on the tag.
- **Tag Ink** (`tag-ink`): dark brown print on manila: tag headings, input text, slot values, checkbox labels, and the select's chevron.
- **Tag Ink Muted** (`tag-ink-2`): secondary print on manila: the tag's lede, field labels, slot titles, fine print, and the find-us terms.
- **Brass** (`brass`): the eyelet rim (4px ring) and the dashed underline beneath placeholder copy on the mat.
- **Brass Deep** (`brass-2`): hardware in shadow. The eyelet's inner and outer hairlines, the bottom border and focus ring of every input on the tag, the dashed border of an empty slot, the accent slot badge on a chip, the pressed slot's inset ring, and the OK message border.

### Tertiary
- **Focus Gold** (`focus`): the focus-visible ring on everything that sits on the mat (2px, offset 3px), link hover, and text selection with mat ink. A state color, never a brand color. The source also aliases it as `--sel-bg` with `--sel-ink` set to mat.
- **Error Orange** (`err`): the border of the error message on the tag. It appears nowhere else.

### Neutral
- **Mat** (`mat`): the page ground, charcoal not black. Also the scrollbar track, the nav's 92% backdrop tint, and the scrollbar thumb's border.
- **Mat Raised** (`mat-2`): the family tab at rest.
- **Tread** (`mat-tread`): the 3.5% white hairlines that form the diamond tread, two repeating gradients at ±45deg on a 9px pitch.
- **Ink** (`ink`): body copy on the mat, headings, nav brand, spec cells, and the color of the page's links.
- **Ink Muted** (`ink-2`): ledes, nav links at rest, the hero sub, deck empty state, step copy, spec column subtitles, and the "Coatings" half of the brand.
- **Ink Faint** (`ink-3`): the deck note, spec row heads, and footer copy.
- **Rule** (`rule`): the scrollbar thumb; the stronger of the two galvanized greys.
- **Rule Hairline** (`rule-2`): every structural hairline: nav bottom, section tops, spec row tops, step cell borders, the wall's border, the sister-shop panel, and the family tab at rest.

### Named Rules
**The Chip Carries the Color Rule.** Chromatic color appears only on a chip face, on a swatch that was filled from a chip, or on the step numerals, which are chips. The chrome of the page (mat, label, manila, brass, rules) is achromatic or earthen and never competes with the catalog.

**The Picked Accent Rule.** The page has no brand accent. The accent on any viewport is whatever the visitor picked; the only system color that behaves like an accent is Focus Gold, and it appears solely as a focus, hover, or selection state.

**The Two Stocks Rule.** Text sits on one of two stocks and takes that stock's ink: label white takes label ink, manila takes tag ink. Mat ink never prints on a strip or a tag, and tag ink never prints on the mat.

## Typography

**Display Font:** Barlow Condensed (with system-ui, sans-serif), self-hosted at 600, 700, 800
**Body Font:** Barlow (with system-ui, sans-serif), self-hosted at 400, 500, 600
**Label/Code Font:** Barlow Condensed 700 for labels, 800 with tabular figures for H-codes

**Character:** A stamped aluminum plate. Condensed, heavy, and set tight at 0.95 line-height so headings read as one pressed object; the body face is the same family uncondensed, so copy and labels share a skeleton and nothing on the page looks borrowed from a different shop.

### Hierarchy
- **Display** (800, clamp(2.4rem, 4.1vw, 3.7rem), 0.95, -0.01em): the hero's one line, "Pick the finish. We'll quote the job." Balanced wrapping (`text-wrap: balance`).
- **Headline** (800, clamp(2.2rem, 4.6vw, 3.6rem), 0.95, -0.01em): section h2s. The hang tag's h2 is the same face at a fixed 2rem.
- **Title** (700, 1.5rem, 0.95): step titles and panel h3s; the sister-shop h3 steps up to 1.9rem. Spec column heads are 800 at 1.7rem on a label strip.
- **Body** (400, 17px, 1.5): paragraphs capped at 68ch, footer at 80ch, spec cells at 34ch. Ledes are 1.1rem in Ink Muted; the hero sub uses 600 for emphasis instead of a second color.
- **Label** (Barlow Condensed 700, 0.95rem, 0.04em, uppercase): field labels and legends on the tag, find-us terms, spec row heads (0.05em). Family tabs use the same face at 1rem / 0.02em; slot titles at 0.8rem / 0.05em; the chip's slot badge at 0.7rem / 0.06em in 800.
- **Code** (Barlow Condensed 800, 0.98rem, 0.02em, tabular-nums): the H-code on a chip label. Pairing codes and step numerals also set `font-variant-numeric: tabular-nums`. The color name beneath a code drops to Barlow 500 at 0.68rem in Label Ink Muted, single line with ellipsis.
- **Nav** (Barlow 500, 0.95rem) for links, with the brand in Barlow Condensed 800 at 1.35rem and its second word in 600 Ink Muted.

### Named Rules
**The Stamped Plate Rule.** Every heading is Barlow Condensed 800 at line-height 0.95 and -0.01em. No heading is lighter than 700 and nothing condensed is set below 0.68rem.

**The Tabular Code Rule.** An H-code is always Barlow Condensed 800 with tabular figures, and the name that follows it is always the body face, smaller and muted. Code first, name second, never the other way.

**The Uppercase Is a Label Rule.** Uppercase is reserved for condensed labels on a stock (tabs, field labels, slot titles, the send button, strip buttons). Headings and body copy are sentence case.

## Layout

The page is one scrolling counter. The hero is a two-column grid, `minmax(0, 1.6fr) minmax(320px, 0.8fr)` with a `clamp(24px, 3.5vw, 56px)` gap: the deck (tabs, wall, note) on the left and the hang tag on the right, sticky at `top: 64px` beneath the sticky nav so the tag follows the visitor while they browse chips. Page gutters are `clamp(16px, 4vw, 56px)` on every band; sections below the hero center a 1180px column, carry an 80px top and bottom (52px under 760px), and are divided by a 1px Rule Hairline top border instead of any background change.

The wall is an auto-fill grid of `minmax(104px, 1fr)` chips at a 12px gap inside 14px padding, which yields seven to eight chips per row at desktop widths; under 980px the cell drops to `minmax(88px, 1fr)` at a 10px gap, and under 480px it locks to four columns at 8px. Family tabs sit above the wall in a wrapping flex row with a 4px gap; under 760px they stop wrapping and scroll horizontally with the scrollbar hidden. Items are a wrapping row of strips at a 10px gap capped at 900px; pairings are an auto-fill grid of `minmax(160px, 1fr)` with a 28px row and 20px column gap; steps are an auto-fit grid of `minmax(220px, 1fr)` whose cells are divided by hairlines rather than gaps. Find-us is a two-column split with a `clamp(24px, 5vw, 72px)` gap.

Breakpoints, as used: 980px (hero collapses to one column, the tag goes static, the fixed bottom bar appears and the body gains 70px of bottom padding), 860px (nav links hide, the brand and CTA remain), 760px (section padding tightens, spec table becomes stacked cards, steps go single column, tabs scroll), 480px (four-column wall), 420px (the name/contact row stacks).

Rhythm inside the tag is tighter than on the mat: fields are 10px apart, slots 8px, check lines 4px, with the tag's own padding at 34px top (clearing the eyelet) and 20px sides. Spacing on the mat moves in 12 / 24 / 28 / 80 steps.

## Elevation & Depth

A hybrid with a physical reading: the mat is flat and everything that is part of the mat (nav, wall, sister panel, section bands) is drawn with a 1px Rule Hairline border and at most a tint, while everything that sits on the mat (chips, label strips, the hang tag, the mobile bar) casts a soft two-layer shadow of a tight contact shadow plus a wide ambient one. Lift is expressed by growing that shadow and translating upward, never by brightening the surface. The wall itself is recessed with a 22% black tint so chips read as resting inside a tray. Light chips carry an inset hairline so a white face does not dissolve into its label.

### Shadow Vocabulary
- **Chip at rest** (`box-shadow: 0 1px 2px rgba(0,0,0,.5), 0 6px 14px rgba(0,0,0,.35)`): chips in the wall, pairing chips, and step numerals.
- **Chip hover** (`box-shadow: 0 2px 3px rgba(0,0,0,.5), 0 12px 22px rgba(0,0,0,.45)`): with `translateY(-3px)`.
- **Chip picked** (`box-shadow: 0 3px 4px rgba(0,0,0,.55), 0 18px 30px rgba(0,0,0,.5)`): with `translateY(-6px) scale(1.04)` and raised z-index.
- **Light chip ring** (`inset 0 0 0 1px rgba(0,0,0,.18)`): added ahead of the rest shadow on chips whose face is lighter than the label; also the filled swatch in a slot or the bar.
- **Strip** (`box-shadow: 0 1px 2px rgba(0,0,0,.5), 0 4px 10px rgba(0,0,0,.3)`): item strips, pairing captions, spec heads, the stamp. The "Add photos" strip uses the contact layer only (`0 1px 2px rgba(0,0,0,.35)`).
- **Hang tag** (`filter: drop-shadow(0 2px 3px rgba(0,0,0,.5)) drop-shadow(0 18px 28px rgba(0,0,0,.5))`): on the tag's wrapper so the shadow follows the notched clip; tightens to `0 12px 22px` under 980px and on the mini tag.
- **Eyelet** (`inset 0 0 0 1px var(--brass-2), 0 0 0 1px var(--brass-2), 0 1px 1px rgba(0,0,0,.35)`): the brass rim's hairlines.
- **Mobile bar** (`box-shadow: 0 -4px 18px rgba(0,0,0,.45)`): the only upward shadow, the bar sits over the page edge.

### Named Rules
**The Objects Cast, Surfaces Don't Rule.** A shadow means the element is a thing lying on the mat (chip, strip, tag, bar). Panels, bands, and tables are part of the mat and get a hairline, never a shadow.

**The Lift Is a Shadow Rule.** Hover and selection raise the object by growing its shadow and translating it up along the one easing; the surface color never changes on lift.

## Shapes

Softly rounded hardware with punched holes. Chips are 5:7 rectangles at a 7px radius with a hole punched at the top-left by a radial-gradient mask (`circle at 13px 13px`, 4.5px clear, 5.2px solid), a diagonal gloss (118deg, 22% white to 16% black) across the face, and, for metallics, a fine repeating diagonal grain blended with overlay. Pairing chips are the same form at 76x104px, rotated -6deg and 5deg and overlapped; step numerals are 46x64px chips; swatches in the slots and bar are the same form at 40x52 and 30x40 with a smaller punch.

The hang tag has its top corners notched by an 18px polygon clip-path, 10px radii above and 6px below, a hole punched at the top center (`circle at 50% 19px`, 5.5px clear), a 20px brass ring with a 4px border around the hole, and a 2px string drawn above it as a vertical gradient from `#d8d5cb` to `#8f8c83`. The mini tag repeats this at 14px notches with the eyelet offset left.

Label strips are 4px; the send button and slot buttons are 5px; inputs, the chip's slot badge, and the focus ring are 3px; panels (wall, sister) are 8px, with the wall's top-left corner squared where the active tab joins it; tabs round only their top corners at 7px. Borders are 1px hairlines in Rule Hairline on the mat and Manila Edge on the tag, with Brass Deep on an input's bottom edge; dashed Brass Deep marks anything waiting to be filled (empty slot swatch, empty slot button) and a dashed brass underline marks placeholder copy.

## Components

### Sample Chip
The signature component and the first field of the quote form. A `button` with `--c` set to the catalog hex, `aspect-ratio: 5/7`, 7px radius, the punched-hole mask, the gloss pseudo-element, and the two-layer rest shadow. Its label strip is pinned to the bottom: Label White, Label Ink, 5px 7px 6px padding, H-code in Code type over the name in Barlow 500 at 0.68rem. A slot badge (Label Ink on Label White, 0.7rem 800 uppercase, 3px radius) sits top-right, hidden until the chip is picked; the accent slot's badge is Brass Deep.
- **Hover:** `translateY(-3px)` and the hover shadow over `.35s` on the system ease.
- **Picked (`data-slot`):** `translateY(-6px) scale(1.04)`, picked shadow, badge fades in from `-4px`.
- **Focus:** Focus Gold 2px ring, 3px offset.
- **Light faces (`.light`):** add the inset hairline ring. **Metallics (`.metal`):** add the grain overlay.

### Label Strip
The secondary surface and the universal control. Label White, Label Ink, 4px radius, strip shadow, Barlow Condensed 700 at 1.05rem with an optional Barlow 400 subline at 0.8rem in Label Ink Muted. Used as item strips, pairing captions (1.1rem title over tabular codes), spec column heads (800 at 1.7rem), the "shop samples" stamp beside a heading, and the chip label itself.

### Buttons
- **Shape:** label strip (4px) for strip buttons, 5px for the send button.
- **Send (primary, on the tag):** Label Ink fill, Label White text, Barlow Condensed 800 at 1.25rem, 0.04em, uppercase, 13px 16px, full width. Hover: pure black and `translateY(-1px)` over `.2s`. Disabled: 60% opacity, no lift. Focus: Brass Deep 2px ring, 3px offset.
- **Strip button (nav CTA, sister link, mobile bar link, "Add photos"):** Label White fill, Label Ink text, 4px radius, 9px 14px (7px 12px to 14px on the smaller ones). Hover: Label Hot. The mobile bar's link inverts to Label Ink on Label White so it reads against the bar.
- **Pairing button:** transparent, the two overlapped chips plus a caption strip; hover lifts the front chip 4px and the back chip 2px; focus ring is Focus Gold at 4px offset with a 6px radius.

### Family Tabs
Deck tabs on the wall's top edge. Mat Raised fill, Ink Muted text, 1px Rule Hairline border with no bottom, 7px top radii, 8px 14px 10px padding, Barlow Condensed 700 at 1rem uppercase. Hover brings the text to Ink over `.15s`; `aria-pressed="true"` turns the tab into a label strip (Label White fill and border, Label Ink text) that joins the wall's squared top-left corner.

### Hang Tag (Cards / Containers)
- **Corner Style:** notched top (18px clip), 10px / 6px radii, eyelet mask and brass rim.
- **Background:** Manila with Tag Ink; the string above it in a `#d8d5cb` to `#8f8c83` gradient.
- **Shadow Strategy:** drop-shadow filter on the wrapper (see Elevation), sticky beneath the nav on desktop, static under 980px.
- **Internal Padding:** 34px 20px 18px; fields 10px apart.
- The find-us mini tag is the same object at 30px 18px 16px with a left-set eyelet. The only other container is the sister-shop panel: part of the mat, 1px Rule Hairline, 8px radius, 22px 24px, no shadow.

### Inputs / Fields (on the tag)
- **Style:** 55% white over manila, 1px Manila Edge border with a Brass Deep bottom edge, 3px radius, 9px 10px padding, Tag Ink text, placeholder in a muted brown. Selects hide the native arrow and draw a 14x9 inline SVG chevron in Tag Ink. Textareas start at 54px and resize vertically.
- **Label:** Barlow Condensed 700 at 0.95rem, 0.04em, uppercase, Tag Ink Muted, 4px above the control.
- **Focus:** Brass Deep 2px outline at 1px offset and the field goes Label Hot.
- **Checkbox:** 18px, 1.5px Brass Deep border, 3px radius, 55% white; checked goes Label Hot and scales in a Label Ink check (clip-path polygon) over `.2s` on the system ease. Its label is Barlow 500 at 0.98rem in Tag Ink.
- **File picker:** the native input is visually hidden; its label is a strip button ("Add photos") beside a count in Tag Ink Muted, with the focus ring forwarded to the strip.
- **Messages:** Label Hot card, 4px radius, 10px 12px, 0.92rem; error bordered in Error Orange with dark red text, success bordered in Brass Deep with Tag Ink text.

### Slot Button (Finish / Accent)
A two-column grid (40px swatch, text) at 7px padding, 62px minimum height, 5px radius, 40% white over manila with a dashed Brass Deep border. The swatch is a 40x52 chip form with its own punch; empty, it is a dashed Brass Deep outline, filled it takes `--c` and the inset hairline. Title in Barlow Condensed 700 at 0.8rem uppercase Tag Ink Muted; value in Barlow 600 at 0.95rem Tag Ink with the color name as a 0.8rem 400 subline. `aria-pressed="true"` makes the border solid, the fill Label Hot, and adds a 2px Brass Deep inset ring. The swatch recolors over `.35s` and the value cross-fades over `.45s`, both on the system ease.

### Navigation
A sticky strip at the top: 92% Mat with a 6px backdrop blur, 10px vertical padding, 1px Rule Hairline bottom. Brand in Barlow Condensed 800 at 1.35rem (second word 600 Ink Muted), links in Barlow 500 at 0.95rem Ink Muted that go to Ink on hover, and a strip-button CTA ("Quote tag") at the right. Under 860px the link list hides. Under 980px a fixed bottom bar (Label White, Label Ink, upward shadow, 10px padding) shows the picked finish beside a 30x40 swatch and a Label Ink strip button that scrolls to the tag.

### Spec Table
Column heads are label strips (800 at 1.7rem) with a Barlow 500 subtitle in Ink Muted; row heads are condensed uppercase labels in Ink Faint at an 11ch width; cells are Ink, 34ch max, divided by Rule Hairline tops with 16px vertical padding. Under 760px the table stacks: each row becomes a hairline-topped block and each cell prints its column name from `data-h` in Barlow Condensed 800 at 1.3rem.

### Motion
One grammar. Easing `cubic-bezier(.16,1,.3,1)` (`--ease`) on every transform and cross-fade: chip lift `.35s`, pairing lift `.35s`, slot swatch `.35s`, slot value `.45s`, checkbox tick `.2s`, send lift `.2s`, slot badge `.25s`. Color-only transitions (tabs `.15s`, send background `.2s`, slot background `.2s`) use the default ease. Smooth anchor scrolling is on and turns off under `prefers-reduced-motion`. There are no keyframes and no scroll-triggered entrances.

## Do's and Don'ts

### Do:
- **Do** keep chromatic color inside chip faces and swatches filled from chips; the chrome stays Mat, Label White, Manila, and Brass.
- **Do** set every H-code in Barlow Condensed 800 with tabular figures and the color name after it in Barlow 500, smaller and muted.
- **Do** build every control as a label strip (Label White, Label Ink, 4px radius) or a chip; a pressed tab, a button, and a chip label are the same object.
- **Do** give anything that lies on the mat the two-layer shadow (`0 1px 2px rgba(0,0,0,.5)` plus a wide ambient layer) and anything that is part of the mat a 1px Rule Hairline border instead.
- **Do** use `cubic-bezier(.16,1,.3,1)` for every lift and cross-fade, `.35s` for lifts and `.45s` for value fades.
- **Do** mark empty and placeholder states with dashed Brass Deep (empty swatch, empty slot) or a dashed brass underline (placeholder copy).
- **Do** ring focus in Focus Gold (2px, 3px offset) on the mat and in Brass Deep on the tag.
- **Do** punch the hole: a chip or a tag without its mask is a rectangle, not a sample.

### Don't:
- **Don't** use gradients as decoration; the only gradients are material: the chip gloss, the metallic grain, the tread hairlines, and the tag's string.
- **Don't** add icon tiles or ornamental glyphs; the only icon on the page is the select's inline chevron.
- **Don't** introduce a brand accent color; the accent on any viewport is the chip the visitor picked, and Focus Gold is a state, not a brand.
- **Don't** use pure black as a ground; the mat is charcoal `mat`, and `#000` appears only as the send button's hover.
- **Don't** add per-section entrances, scroll reveals, or keyframe animation; lifts and cross-fades on the one easing are the whole grammar.
- **Don't** print mat ink on a strip or a tag, or tag ink on the mat; each stock has its own ink.
- **Don't** change a surface's color to show lift; grow the shadow and translate.
