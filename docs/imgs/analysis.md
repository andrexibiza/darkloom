# Illustration Analysis — Darkloom Documentation Suite
## 2026-07-23

### Content Summary

Six documents, 34 PRs, one project:

| Document | Type | Core Arguments |
|----------|------|---------------|
| README.md | Technical overview | 32-PR hardening battery, 17 leaks fixed, post-quantum transport, fail-closed policy |
| MANIFESTO.md | Technical manifesto | Origin story, 19-PR first wave, 13-PR second wave, cryptographic stack, leak audit |
| TECHNICAL_REFERENCE.md | Module reference | 13 modules, proxy resolution chain, self-healing topology, API reference |
| DARKLOOM_PROTOCOL.md | Protocol specification | Post-quantum hybrid handshake, MAPE-K loop, MCP transport, STIG compliance |
| OPEN_LETTER_SAM_ALTMAN.md | Public letter | Five-layer breach prevention, Sol incident analysis, SF relocation intent |
| OPEN_LETTER_NOUS_RESEARCH.md | Public letter | Hermes integration, MAPE-K governance, SF relocation intent |

### Content Type Signals

- **Dominant:** Technical / AI / Security Architecture
- **Secondary:** Manifesto / Editorial (open letters), Tutorial (integration surface), Framework (protocol)
- **Purpose:** Information + conviction + recruitment

### Key Concepts That Need Visualization

1. **Five-Layer Cryptographic Stack** (MANIFESTO §3.1, TECH_REF §1.2) — VPN → obfs4 → Tor circuit → SOCKS5 → TLS
2. **Post-Quantum Hybrid Handshake** (PROTOCOL §2) — ECDH + NTRU-Encrypt KEM → HKDF-SHA256 session key
3. **Network Policy Authorization Gate** (PROTOCOL §4, TECH_REF §3.13) — 15 channels, default-deny, fail-closed
4. **MAPE-K Self-Healing Loop** (PROTOCOL §5) — Monitor → Analyze → Plan → Execute → Knowledge
5. **Sol Breach vs Darkloom Prevention** (Sam Letter) — Five breach steps, five intercepts
6. **32-PR Hardening Battery** (MANIFESTO §6-7, README) — Two waves, cumulative test growth
7. **17-Leak Audit** (README, MANIFESTO §8) — Transport/policy layer fixes
8. **MCP Transport Architecture** (PROTOCOL §3) — SSE vs stdio, distributed vs local
9. **Risk-Confidence Matrix** (PROTOCOL §5) — Agent trust levels
10. **Gateway + 23-Platform Architecture** (README) — Tor daemon → ALL_PROXY → 23 adapters
11. **Harvest-Then-Decrypt Defense** (PROTOCOL §2) — Classical vs post-quantum timeline
12. **Self-Healing Watchdog** (TECH_REF §6) — 15s health check, exponential backoff, circuit rotation

### Recommended Illustration Positions

| # | Position (Doc) | Concept | Type | Style |
|---|---------------|---------|------|-------|
| 1 | MANIFESTO §3.1 | Five-Layer Crypto Stack | framework | blueprint |
| 2 | PROTOCOL §2 | Hybrid Handshake (ECDH + NTRU) | framework | blueprint |
| 3 | PROTOCOL §4 / TECH_REF §3.13 | Network Policy Gate (authorize flow) | flowchart | blueprint |
| 4 | PROTOCOL §5 | MAPE-K Self-Healing Loop | framework | blueprint |
| 5 | Sam Letter §1-6 | Sol Breach → Darkloom Intercept | comparison | screen-print |
| 6 | README / MANIFESTO §6-7 | 32-PR Hardening Battery | infographic | blueprint |
| 7 | README | 17-Leak Audit Status | infographic | editorial |
| 8 | PROTOCOL §3 | MCP Transport (SSE vs stdio) | comparison | vector-illustration |
| 9 | PROTOCOL §5 | Risk-Confidence Matrix | framework | blueprint |
| 10 | README | Gateway + 23 Platforms Architecture | framework | blueprint |
| 11 | PROTOCOL §2 | Harvest-Then-Decrypt Timeline | timeline | blueprint |
| 12 | TECH_REF §6 | Self-Healing Watchdog Loop | flowchart | blueprint |
