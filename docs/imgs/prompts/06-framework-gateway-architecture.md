---
illustration_id: 06
type: framework
style: blueprint
---

Darkloom Gateway Architecture — Tor Daemon → 23 Platform Adapters

STRUCTURE: Left-to-right flow with branching

LEFT: "Tor Expert Bundle 15.0.19" box → "lyrebird + obfs4 bridges" label → "SOCKS5 127.0.0.1:9050" box

CENTER: "ALL_PROXY=socks5://127.0.0.1:9050" injection arrow → "Hermes Gateway" large central node

RIGHT: Branching tree to 23 platform nodes, each with status indicator:
- Row 1 (SOCKS5 ✅): Telegram, Discord, Matrix, Photon (iMessage), WhatsApp, LLM API, Web Tools, Browser, Subagents, Signal, SMS, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, WeChat, Raft/API/Webhooks
- Row 2 (⚠️ HTTP only): Slack
- Row 3 (🔒 Policy-blocked): Email, IRC

Below: "policy.py" authorization gate symbol at the boundary between Gateway and platforms.

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Tor daemon node in purple (#7D4698). Gateway node larger, in darker blue (#0f2440) with cyan border. Green checkmark platforms, amber warning for Slack, red for blocked.

ASPECT: 16:9

Clean composition. Technical schematic. Monospace labels for all protocol names. No gradients. Grid-lined background.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
