---
illustration_id: 05
type: infographic
style: blueprint
---

Self-Healing Watchdog — Layered Health Verification & Recovery

LAYOUT: Three horizontal panels

PANEL 1 — Health Monitoring (left):
- Vertical timeline: "0s → 15s → 30s → 45s → 60s"
- Four check layers stacked: "Layer 1: Process Health (is tor.exe alive?)", "Layer 2: SOCKS5 Handshake (TCP connect 127.0.0.1:9050)", "Layer 3: Bootstrap Verified (authenticated circuit)", "Layer 4: Exit Route Verified (check.torproject.org)"
- Green checkmarks or red X marks on each layer per check cycle

PANEL 2 — Exponential Backoff (center):
- Bar chart showing restart attempts: "Attempt 1: 10s wait", "Attempt 2: 20s", "Attempt 3: 40s", "Attempt 4: 80s", "Attempt 5: 160s (max)"
- Total label: "Max recovery time: 310s"
- Curve overlay showing exponential growth

PANEL 3 — Circuit Rotation (right):
- Circular timeline: "10-minute cycle"
- Three circuit diagrams (Circuit A → Circuit B → Circuit C) with rotation arrows
- "NEWNYM signal via ControlPort (cookie-authenticated)" label
- "Fallback: daemon restart" label

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Green (#4caf50) for healthy checks, amber (#ffb74d) for degraded, red (#ef5350) for failed.

ASPECT: 16:9

Clean composition. Technical schematic. Monospace labels. No gradients. Grid-lined background.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
