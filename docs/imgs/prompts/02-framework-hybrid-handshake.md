---
illustration_id: 02
type: framework
style: blueprint
---

Post-Quantum Hybrid Handshake — ECDH + NTRU-Encrypt KEM at λ=128

STRUCTURE: Client-server handshake diagram, left-to-right flow

LEFT SIDE (Client):
- Box 1: "ECDH Keygen (84 µs)" → produces 84-byte client data
- Box 2: "NTRU Encapsulate (577 µs)" → produces 609-byte KEM ciphertext
- Combined: "693 bytes Client → Server"
- Total client cost label: "661 µs init + 218 µs finish = 74% bias"

CENTER:
- "XOR Combiner" node where ECDH shared secret and NTRU decapsulated secret are combined
- "HKDF-SHA256 Extraction" node (RFC 5869)
- Output: "Session Key — λ=128"

RIGHT SIDE (Server):
- Box 1: "ECDH Keygen (263 µs)" → produces 64-byte server data
- Box 2: "NTRU Decapsulate (43 µs)" → produces 609-byte response
- Combined: "673 bytes Server → Client"

Below main diagram: small comparison table —
  "ntor (classical): 527 µs total, 84+64 bytes"
  "hybrid (post-quantum): 1,185 µs total, 693+673 bytes"

LABELS: Actual timing numbers (661 µs, 306 µs, 218 µs). Actual byte sizes (84, 693, 64, 673). λ=128 security level.

COLORS: Blueprint blue (#1a3a5c) background with white (#e8f0f8) grid. Client side in teal (#4fc3f7) accent. Server side in amber (#ffb74d) accent. HKDF node in white outline highlight.

ASPECT: 16:9

Clean composition with generous white space. Grid-lined technical schematic background. Monospace labels. No gradients. Engineering aesthetic.
Color values (#hex) and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text in the image.
