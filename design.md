---
name: Deep Intel
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#3f4947'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#6f7977'
  outline-variant: '#bfc9c6'
  surface-tint: '#266861'
  primary: '#003732'
  on-primary: '#ffffff'
  primary-container: '#005049'
  on-primary-container: '#81c1b7'
  inverse-primary: '#92d2c9'
  secondary: '#5e5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e2e2e2'
  on-secondary-container: '#646464'
  tertiary: '#2f3131'
  on-tertiary: '#ffffff'
  tertiary-container: '#454747'
  on-tertiary-container: '#b4b5b5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#aeefe5'
  primary-fixed-dim: '#92d2c9'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#e2e2e2'
  secondary-fixed-dim: '#c6c6c6'
  on-secondary-fixed: '#1b1b1b'
  on-secondary-fixed-variant: '#474747'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: '0'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.08em
  mono-data:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: -0.01em
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  gutter: 24px
  margin: 32px
---

## Brand & Style

The design system is engineered for security analytics environments where clarity and authority are paramount. It follows a **Minimalist** and **High-Contrast** design movement, prioritizing rapid information processing and error reduction. The brand personality is clinical, disciplined, and unwavering. 

The aesthetic is characterized by a "void-and-light" philosophy: vast white space represents the canvas of data, while deep teal and black represent the surgical precision of the analysis. This design system avoids all decorative flourishes, including gradients and soft shadows, to maintain a strictly professional and high-stakes operational tone.

## Colors

This design system utilizes a restricted, high-contrast palette to drive focus. 
- **Primary Teal (#005049):** Reserved strictly for interactive elements, primary actions, and critical data highlights. It serves as the "active" state indicator throughout the interface.
- **Pure Black (#000000):** Used for primary headings and body text to ensure maximum legibility and an authoritative voice.
- **Pure White (#FFFFFF):** The standard background for all surfaces, creating a "clean room" environment for data visualization.
- **Light Gray (#F5F5F5):** The only secondary surface color allowed, used solely for subtle structural containment or to differentiate secondary sidebar regions from the main dashboard workspace.

## Typography

The design system uses **Inter** exclusively. The typographic hierarchy is designed to mirror the structural nature of security logs. 
- **Headlines:** Set in Bold with tighter letter spacing for an impactful, institutional feel.
- **Body:** Set in Regular for maximum readability during long-form analysis. 
- **Labels:** Small, uppercase labels with increased letter spacing are used for metadata and table headers to distinguish them from actionable data.
- **Teal Typography:** Use the primary teal color only for links, active navigation items, or highlighted search terms within logs.

## Layout & Spacing

The design system employs a **Fixed Grid** model within a flexible viewport container. 
- **Grid:** A 12-column system with a 24px gutter. 
- **Rhythm:** All spacing (padding, margins) must be a multiple of the 4px base unit. 
- **Density:** High-density layouts are preferred for analytics views. White space should be used strategically to separate logical modules rather than purely for aesthetics. Large 48px margins are used to frame the main workspace, emphasizing the "dashboard" as a controlled environment.

## Elevation & Depth

This design system avoids traditional shadows. Depth is conveyed entirely through **Low-contrast outlines** and **Tonal layering**. 
- **Borders:** Surfaces are defined by 1px solid borders in Black (for high-priority containers) or Light Gray (for secondary containment).
- **Layers:** Interaction depth is achieved through simple color fills. A hovered element should change from a White background to a very Light Gray background, or from a Light Gray border to a Teal border.
- **Focus:** Active states are represented by a 2px solid Teal stroke, ensuring the user's focus is always anchored to the current operation.

## Shapes

The design system utilizes **Sharp (0px)** corners for all structural components, including cards, inputs, and layout modules. This reinforces the architectural and authoritative nature of the security platform. 

A very slight exception is permitted for small interactive indicators like radio buttons or specific iconography, but buttons and larger containers must remain strictly rectangular to maintain the minimalist, grid-aligned aesthetic.

## Components

- **Buttons:** Primary buttons are Solid Teal with White text. Secondary buttons are White with a 1px Black border and Black text. Ghost buttons use Teal text with no background.
- **Inputs:** Strictly rectangular 1px Black border. Upon focus, the border transitions to 2px Teal. Labels are placed above the input in `label-caps`.
- **Chips/Tags:** Used for status. High-priority alerts use Solid Black with White text. Normal status uses White with a 1px Light Gray border.
- **Cards:** No shadows. Use a 1px Light Gray border. Card headers should be separated by a 1px horizontal rule.
- **Data Tables:** High-density. Rows are separated by 1px Light Gray lines. Header text is `label-caps` in Black. Hovered rows should have a very Light Gray (#F5F5F5) background.
- **Log Viewer:** Monospaced-style Inter (`mono-data`) with Teal highlights for matched search strings. Use strict vertical alignment to ensure scanability.