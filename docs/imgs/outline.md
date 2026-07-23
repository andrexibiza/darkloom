---
type: mixed
density: rich
style_primary: blueprint
style_secondary: screen-print
image_count: 14
generated: 2026-07-23T23:00:00Z
---

# Darkloom Documentation — Illustration Outline

## Technical Architecture (Blueprint Style)

### Illustration 1
**Position**: MANIFESTO.md §3.1 — "The Five-Layer Stack"
**Purpose**: Show the complete cryptographic stack from VPN through TLS
**Visual Content**: Five stacked horizontal layers with protocol labels, key sizes, and RFC citations
**Type**: framework
**Style**: blueprint
**Filename**: 01-framework-crypto-stack.png

### Illustration 2
**Position**: DARKLOOM_PROTOCOL.md §2 — "Post-Quantum Hybrid Handshake"
**Purpose**: Visualize the ECDH + NTRU-Encrypt KEM → HKDF-SHA256 session key derivation
**Visual Content**: Client/server handshake diagram with byte sizes, timing, the XOR combiner, and HKDF extraction
**Type**: framework
**Style**: blueprint
**Filename**: 02-framework-hybrid-handshake.png

### Illustration 3
**Position**: DARKLOOM_PROTOCOL.md §4 / TECHNICAL_REFERENCE.md §3.13
**Purpose**: Show the authorize() gate logic — 15 channels, four categories, default-deny
**Visual Content**: Flowchart: channel enters → category check → proxy_aware check → allow/deny
**Type**: flowchart
**Style**: blueprint
**Filename**: 03-flowchart-network-policy.png

### Illustration 4
**Position**: DARKLOOM_PROTOCOL.md §5 — "MAPE-K Self-Healing Loop"
**Purpose**: The autonomous governance control loop
**Visual Content**: Five-node circular diagram — Monitor → Analyze → Plan → Execute → Knowledge → (back to Monitor)
**Type**: framework
**Style**: blueprint
**Filename**: 04-framework-mapek-loop.png

### Illustration 5
**Position**: TECHNICAL_REFERENCE.md §6 — "Self-Healing Topology"
**Purpose**: Watchdog health check, exponential backoff, circuit rotation
**Visual Content**: Three-panel schematic: health monitoring timeline, backoff curve, circuit rotation cycle
**Type**: infographic
**Style**: blueprint
**Filename**: 05-infographic-watchdog.png

### Illustration 6
**Position**: README.md — "Architecture / Gateway + 23 Platforms"
**Purpose**: Replace existing mermaid diagram with a richer visualization
**Visual Content**: Tor daemon → ALL_PROXY injection → Hermes Gateway → 23 platform adapters with status indicators
**Type**: framework
**Style**: blueprint
**Filename**: 06-framework-gateway-architecture.png

### Illustration 7
**Position**: DARKLOOM_PROTOCOL.md §3 — "MCP Transport Architecture"
**Purpose**: SSE vs stdio comparison for agent-to-tool communication
**Visual Content**: Split comparison: distributed SSE (cloud) vs local stdio (filesystem), with latency, security, auth labels
**Type**: comparison
**Style**: blueprint
**Filename**: 07-comparison-mcp-transport.png

### Illustration 8
**Position**: DARKLOOM_PROTOCOL.md §5 — "Risk-Confidence Matrix"
**Purpose**: Agent trust levels — Senior, Junior, Intern, Restricted
**Visual Content**: 2×2 matrix grid with trust escalation arrows and action labels
**Type**: framework
**Style**: blueprint
**Filename**: 08-framework-risk-matrix.png

### Illustration 9
**Position**: README.md / MANIFESTO.md §8-9 — "17 Leaks, 32 PRs, 105 Tests"
**Purpose**: Cumulative hardening battery summary
**Visual Content**: Bar chart — leak status (17/17 fixed), PR count (32), test growth (24 → 105)
**Type**: infographic
**Style**: editorial
**Filename**: 09-infographic-hardening-battery.png

### Illustration 10
**Position**: DARKLOOM_PROTOCOL.md §2 — "Harvest-Then-Decrypt Timeline"
**Purpose**: Show the temporal threat: traffic captured today, decrypted by quantum computer in 2035
**Visual Content**: Horizontal timeline: 2026 (traffic harvested) → 2035 (Shor's algorithm breaks ECDH) → session key protected by NTRU
**Type**: timeline
**Style**: blueprint
**Filename**: 10-timeline-harvest-decrypt.png

## Open Letters (Screen-Print Style)

### Illustration 11
**Position**: OPEN_LETTER_SAM_ALTMAN.md — "The Breach vs The Fence"
**Purpose**: Side-by-side: Sol's five breach steps on the left, Darkloom's five intercepts on the right
**Visual Content**: Split duotone poster — red/black left (breach), teal/cream right (defense). Five connecting arrows showing intercept points
**Type**: comparison
**Style**: screen-print
**Filename**: 11-comparison-sol-breach.png

### Illustration 12
**Position**: OPEN_LETTER_SAM_ALTMAN.md §9 — "You built the raptors. Darkloom is the fence that holds."
**Purpose**: Cinematic poster visualizing the core metaphor
**Visual Content**: Silhouette composition — a contained shape behind a lattice grid structure. Dark teal and terracotta duotone
**Type**: scene
**Style**: screen-print
**Filename**: 12-scene-raptors-fence.png

### Illustration 13
**Position**: OPEN_LETTER_NOUS_RESEARCH.md §2 — "The Five-Layer Prevention"
**Purpose**: Show the five intercept layers in Nous Research brand colors
**Visual Content**: Five concentric rings — outermost (policy gate) to innermost (post-quantum). Each ring labeled with the breach step it blocks
**Type**: framework
**Style**: screen-print
**Filename**: 13-framework-five-layers.png

### Illustration 14
**Position**: OPEN_LETTER_NOUS_RESEARCH.md §6 — "Darkloom × Hermes Integration Surface"
**Purpose**: Show the three integration points: gateway wrapper, policy patches, MCP server
**Visual Content**: Triptych composition — three panels showing each integration point with module names and line numbers
**Type**: framework
**Style**: screen-print
**Filename**: 14-framework-integration-surface.png
