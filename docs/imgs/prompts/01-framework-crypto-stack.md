---
illustration_id: 01
type: framework
style: blueprint
---

Darkloom Five-Layer Cryptographic Stack — Architecture Diagram

STRUCTURE: Vertical stack, five horizontal layers from bottom to top

LAYERS (bottom to top):
- Layer 1 (VPN): WireGuard — ChaCha20-Poly1305 (RFC 7539 §2.8). Label: "VPN — WireGuard · ChaCha20-Poly1305"
- Layer 2 (Bridge Transport): obfs4 — Elligator2 encoding, ntor handshake, lyrebird PT. Label: "obfs4 Bridges — Elligator2 · ntor · lyrebird"
- Layer 3 (Tor Circuit): 3-hop onion, ntor handshake, Curve25519 key exchange (Proposal 216). Label: "Tor Circuit — 3-hop · Curve25519 · NEWNYM"
- Layer 4 (Transport Proxy): SOCKS5 — TCP-only, rdns=True (RFC 1928 §3-4). Label: "SOCKS5 — 127.0.0.1:9050 · rdns=True · TCP-only"
- Layer 5 (Application): TLS 1.3 — AEAD ciphers (RFC 8446 §2). Label: "TLS 1.3 — AEAD · Certificate Validation"

Between layers: up-arrow connectors showing encapsulation flow. Left side: adversary class labels matching each layer (ISP-level DPI, Bridge enumerator, Correlation attacker, etc.). Right side: RFC/Proposal citations.

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid lines and schematic lines. Layer blocks in darker blue (#0f2440). White monospace labels. Connector arrows in cyan (#4fc3f7).

STYLE: Technical schematic. Grid-lined background. Precise line work. Engineering aesthetic. Monospace typography for all labels. No gradients. No shadows. Clean, cold, architectural.

ASPECT: 16:9

Clean composition with generous white space. Simple or no background. Main elements centered or positioned by content needs.
Text should be large and prominent with handwritten-style fonts. Keep minimal, focus on keywords.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
