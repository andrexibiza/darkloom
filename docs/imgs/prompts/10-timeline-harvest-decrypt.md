---
illustration_id: 10
type: timeline
style: blueprint
---

Harvest-Then-Decrypt Defense — Post-Quantum Timeline

DIRECTION: Horizontal timeline, left to right

TIMELINE EVENTS:
- 2026 (left): "Traffic Harvested — Encrypted agent communications captured and stored by adversary. Classical ECDH protects session keys... for now." Icon: data capture symbol (disk/archive)
- 2030-2035 (center, largest marker): "Shor's Algorithm Matures — Quantum computers reach sufficient qubit count and error correction to run Shor's algorithm against captured ECDH ciphertexts. ALL classical key exchange retroactively broken." Icon: quantum computer symbol (superposition/cube). Large WARNING indicator. Red glow.
- 2035+ (right, protected zone): "Session Key Protected — NTRU-Encrypt (ntruees443ep1) component of hybrid handshake remains secure. Shor's algorithm provides no polynomial-time attack on lattice-based KEM. Harvested ciphertexts remain opaque. λ=128 intact." Icon: shield/lock symbol. Green zone.

Above timeline: "Hybrid Handshake: Session Key = HKDF-SHA256(ECDH_secret ⊕ NTRU_decapsulated_secret)"

Below timeline: "The 658 µs of additional client computation is not a cost. It is insurance against the quantum future."

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Left zone in muted teal. Center danger zone in red (#ef5350). Right protected zone in green (#4caf50). Timeline spine in white.

ASPECT: 16:9

Clean composition. Technical schematic. Monospace labels. No gradients. Grid-lined background.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
