---
name: Obsidian Intelligence
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#adc6ff'
  on-secondary: '#002e6a'
  secondary-container: '#0566d9'
  on-secondary-container: '#e6ecff'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#e29100'
  on-tertiary-container: '#523200'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  display-lg:
    fontFamily: Outfit
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  data-tabular:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-page: 40px
  container-padding: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

This design system is engineered for the high-stakes environment of commercial real estate intelligence. The personality is authoritative, precise, and sophisticated—blending the density of a financial terminal with the airy clarity of modern spatial AI. 

The aesthetic follows an **Ultra-Sleek Minimalist** approach with **Glassmorphic** depth. It utilizes high-contrast data visualization against deep, oceanic slates to reduce cognitive load during long analytical sessions. Every interface element is designed to feel like a precision instrument: sharp, responsive, and premium.

## Colors

The palette is anchored by **Slate Dark (#0B0F17)** as the base environment, providing a true-black foundation that allows vibrant data points to pop. 

- **Primary (Electric Emerald):** Reserved for high-performing assets and positive growth indicators.
- **Secondary (Cobalt Blue):** Used for active states, primary actions, and navigational focus.
- **Surface (Obsidian):** Elevated containers use #151C28 to distinguish themselves from the background.
- **Borders:** All surfaces utilize a 1px crisp border in a semi-transparent white (8-10% opacity) to define edges without adding visual bulk.

## Typography

The system utilizes **Outfit** for headlines to provide a modern, geometric feel, while **Inter** handles all functional and body text for maximum legibility. 

A critical requirement is the use of **Tabular Figures** (`tnum`) for all financial and metric data. This ensures that columns of numbers align perfectly in tables and dashboards, facilitating rapid visual scanning. Labels should be kept concise, often utilizing the `label-caps` style for secondary metadata to maintain a clean hierarchical structure.

## Layout & Spacing

This design system uses a **Fluid Grid** with fixed maximum widths for content readability. The layout rhythm is based on a 4px baseline, ensuring all elements relate proportionally.

- **Desktop:** 12-column grid with 24px gutters. Content is often divided into a "Global Navigation" sidebar, a "Contextual Inspector" right-panel, and a "Main Intelligence" central canvas.
- **Mobile/Tablet:** On smaller screens, panels collapse into a drawer system or bottom sheets. Margins reduce to 16px.
- **Alignment:** Financial data must be right-aligned in tables to ensure decimal points and currency symbols create a clean vertical line.

## Elevation & Depth

Depth is communicated through **Glassmorphism** rather than traditional heavy shadows.

- **Level 0 (Background):** Slate Dark (#0B0F17) – The canvas.
- **Level 1 (Card/Surface):** Obsidian (#151C28) with a 1px border (`rgba(255,255,255,0.08)`).
- **Level 2 (Floating/Modals):** Obsidian surface with a background blur (12px - 20px) and a subtle 20% opacity glow matching the primary or accent color to indicate focus.

Shadows, when used for modals, are extra-diffused: `0 20px 40px rgba(0, 0, 0, 0.4)`. The "Glass" effect is achieved via `backdrop-filter: blur(12px)` on semi-transparent surface layers.

## Shapes

To maintain the "Sleek/Professional" feel, the system uses **Soft (0.25rem)** roundedness for small components like inputs and checkboxes, and **Rounded (0.5rem)** for larger cards and containers. Avoid pill-shaped buttons unless used for status tags (chips). The sharp, geometric nature of the icons and font should be mirrored in these tight corner radii to reflect a technical, architectural character.

## Components

### Buttons & Inputs
- **Primary Action:** Solid Cobalt Blue with white text. Hover state adds a subtle outer glow.
- **Secondary Action:** Ghost style (transparent background, 1px border) with clear text.
- **Inputs:** Darker than the surface (#0D121C), with 1px borders that transition to Emerald or Blue on focus.

### Data Visualization
- **Cards:** Utilize a header area with `label-caps` typography and a footer area for "last updated" metadata.
- **Status Chips:** Small, pill-shaped indicators with low-opacity backgrounds (e.g., 10% Emerald background with 100% Emerald text) for "High Rank" or "Low Risk" status.
- **Data Tables:** Zebra striping is avoided in favor of 1px horizontal dividers. Row hover states use a subtle 4% white overlay to highlight the active data line.

### Intelligence Specifics
- **Score Indicators:** Large `display-lg` numbers in Electric Emerald for property rankings.
- **Trend Arrows:** Minimalist 1px stroke arrows (up/down) to indicate market movement.