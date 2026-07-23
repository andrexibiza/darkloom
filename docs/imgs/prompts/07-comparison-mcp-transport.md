---
illustration_id: 07
type: comparison
style: blueprint
---

MCP Transport Architecture — SSE (Distributed) vs stdio (Local)

LAYOUT: Split comparison, left-right

LEFT SIDE — "SSE Transport (Distributed)":
- Icon: cloud/globe
- Communication: "Bi-directional — SSE Stream + POST /messages/"
- Latency: "Higher — network overhead"
- OpenAPI: "Naturally compatible — cloud-ready"
- Security: "Supports TLS/HTTPS and proxies"
- Deployment: "Cloud-ready — remote access"
- Status: green checkmark

RIGHT SIDE — "stdio Transport (Local)":
- Icon: terminal/filesystem
- Communication: "Local inter-process streams"
- Latency: "Lower — in-process efficiency"
- OpenAPI: "Requires proxies (mcp-proxy)"
- Security: "Inherently insecure across environments"
- Deployment: "Filesystem access — local only"
- Status: amber warning

CENTER DIVIDER: Vertical dashed line with "vs" label at center

BOTTOM: Shared label — "Both denied in strict mode without verified proxy transport (policy.py §3.13)"

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Left side teal accent (#4fc3f7). Right side amber accent (#ffb74d). White text labels. Monospace for technical terms.

ASPECT: 16:9

Clean composition. Technical schematic. No gradients. Grid-lined background.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
