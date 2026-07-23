---
illustration_id: 03
type: flowchart
style: blueprint
---

Darkloom Network Policy — Central Authorization Gate (authorize() flow)

LAYOUT: Top-down decision flowchart

START: "Network Operation Requested" node at top

DECISION 1: "TOR_STRICT_MODE=1?" → NO branch: "ALLOW (no-op)" → green terminal
→ YES branch: continue downward

DECISION 2: "Channel in enum?" → NO branch: "DENY — Unknown channel" → red terminal with label "NetworkPolicyError"
→ YES branch: continue

DECISION 3: "Unsupported? (UDP/SMTP/IMAP/IRC)" → YES branch: "DENY — Protocol limitation" → red terminal
→ NO branch: continue

DECISION 4: "Explicit direct? (Tor bootstrap/control)" → YES branch: "ALLOW" → green terminal
→ NO branch: continue

DECISION 5: "proxy_aware=True?" → NO branch: "DENY — Non-proxy-aware" → red terminal with label "Blocks LLM, MCP, execute_code in strict mode"
→ YES branch: continue

DECISION 6: "Valid proxy URL?" → NO branch: "DENY — No valid proxy" → red terminal
→ YES branch: "ALLOW — Verified transport" → green terminal

Right sidebar: 15 channel labels in a column — HTTP, MCP, GATEWAY, PLATFORM, BROWSER, WEB_TOOL, LLM, SUBPROCESS, RAW_SOCKET, UDP_VOICE, SMTP, IMAP, IRC, TOR_BOOTSTRAP, TOR_CONTROL — each color-coded by category (proxy-required=amber, unsupported=red, explicit-direct=green).

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Decision diamonds in white outline. Green terminals (#4caf50), red terminals (#ef5350). Flow arrows in cyan (#4fc3f7).

ASPECT: 16:9

Clean composition with generous white space. Technical schematic. Monospace labels. No gradients.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
