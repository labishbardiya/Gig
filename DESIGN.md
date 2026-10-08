---
name: GIG
description: White conversational interface with the supplied ocean background.
colors:
  bg: "#fff"
  surface: "#f6f6f5"
  line: "#dededb"
  text: "#242624"
  muted: "#626660"
  cyan: "#256455"
  danger: "#a03333"
typography:
  body:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "15px"
    lineHeight: 1.65
rounded:
  field: "8px"
  panel: "16px"
  bubble: "20px"
  composer: "28px"
components:
  scan-panel:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.panel}"
    padding: "20px"
---

# Design System: GIG

## Overview

**Creative North Star: "White ChatGPT-like conversation"**

The user's pinned direction is a white, phone-first conversation over their supplied ocean loop. System typography and charcoal controls keep the interface familiar. The ocean is decorative; actual status is expressed through text and controls.

**Key Characteristics:**

- White reading surfaces and restrained charcoal controls.
- Optional local ocean motion and no external font requests.
- Explicit capture actions and review-before-save.

The shipped cascade loads `phone_app/app.css` first and `phone_app/white.css` second. The latter owns the replacement visual layer.

## Colors

Charcoal carries text and primary actions. Muted green (`cyan` in the existing CSS) carries focus and links. Pale neutral surfaces and fine gray borders separate fields. Red denotes errors and active privacy/capture states. Preserve the existing semantic custom properties.

## Typography

Use the system sans-serif stack. Conversation text uses the body role above. Opening headlines use medium weight, tight tracking and a fluid 28–40px size, resolving to 30px on narrow screens. Status text is 14px; supporting text is 11–13px.

## Layout

The centered outer shell caps at 1120px with 32px horizontal padding. Conversation content caps at 780px; pairing caps at 430px. At 600px and below, horizontal padding becomes 18px. Bottom padding accommodates the safe area. A 900px breakpoint increases the opening stage height. Conversation scrolls within 42dvh, or 40dvh on narrow screens. After the first message the intro compacts and hides its headline, hint and orb.

## Elevation & Depth

The white layer uses borders and pale fills rather than card shadows. A white gradient wash softens the fixed ocean video. Assistant responses have a nearly opaque white fill; the composer and review panel are white. Camera captions retain a dark overlay for legibility.

## Shapes

Rounded message bubbles and the pill composer contrast with compact rounded scan fields. Camera, microphone and send controls are circular. Scan actions are pills; review content sits in a rounded bordered panel.

## Components

The composer combines a flexible text field with a dark circular send button. Camera and stop controls are 44px circles; the microphone is 50px and red while listening. User messages align right with a pale gray fill. Scan review preserves the preview, editable extraction, destination and format choices before explicit saving.

Keyboard focus uses a 2px muted-green outline with a 3px offset; the composer input uses zero offset. Buttons dim on hover; disabled controls use reduced opacity. Background motion has an explicit pause control, pauses when hidden and is hidden under reduced-motion preferences. Other animations are also disabled under reduced motion.

## Do's and Don'ts

- Do preserve the supplied ocean asset and white conversation surfaces.
- Do preserve pairing, scan review, private saving and privacy stop behavior.
- Don't add fictional history, agent progress or connection claims.
- Don't substitute stock media or introduce third-party fonts.
