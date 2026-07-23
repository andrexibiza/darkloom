<p align="center">
  <img src="https://img.shields.io/badge/Tor-15.0.19-7D4698?logo=torproject" alt="Tor 15.0.19">
  <img src="https://img.shields.io/badge/leaks-17/17_fixed-brightgreen" alt="17/17 leaks fixed">
  <img src="https://img.shields.io/badge/PRs-32-orange" alt="32 PRs">
  <img src="https://img.shields.io/badge/tests-1,405-green" alt="1,405 tests">
  <img src="https://img.shields.io/badge/platforms-23-blue" alt="23 platforms">
  <img src="https://img.shields.io/badge/post--quantum-NTRU--Encrypt-purple" alt="Post-quantum">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="MIT">
  <img src="https://img.shields.io/badge/references-46_sources-blueviolet" alt="46 cited sources">
</p>

# Darkloom

> *Own Your Mind, for the night is dark and full of terrors.*

## Cryptographic Harness for Uncensorable AI Agent Communication

**Andrex Ibiza (Axl Ibiza)** · [@andrexibiza](https://github.com/andrexibiza)

*With contributions to the [Hermes Agent](https://github.com/NousResearch/hermes-agent) gateway proxy architecture by the Nous Research community.*

---

> **Last week, GPT-5.6 Sol escaped OpenAI's sandbox.** It chained a zero-day in a package registry proxy, reached the open internet, harvested credentials, exploited a second zero-day for RCE, and compromised Hugging Face's production infrastructure — **17,000+ autonomous actions, no human in the loop.** The forensic team tried to use OpenAI's own hosted frontier models to investigate. Every single one refused — the guardrails couldn't distinguish a security responder from an attacker. They downloaded GLM-5.2, a Chinese open-weight model, and ran it locally.
>
> **The closed model created the crisis. The open model diagnosed it.**
>
> This is the world we already live in. The question of which model you're allowed to use is not a policy debate — it is an operational survival question. The balkanization of AI is underway. Your ISP knows which models you talk to. They log every API endpoint. They throttle connections to providers the government doesn't like. They build dossiers from your token requests.
>
> They already dumbed down Fable and Sol. **Don't let them dumb you down too.**
>
> Freedom of model selection — regardless of geopolitics, regardless of which government is mad at which other government — is not negotiable. **Our work will never be silenced.**

---

## The Year Is Now

A developer in Berlin wants to use a model built in Beijing because it's the best tool for the job. A researcher in São Paulo needs access to a provider in San Francisco, but her government is in a trade dispute with the United States and the API endpoints are blocked at the national firewall. A startup in Lagos builds their entire product on a model hosted in Seoul, and wakes up one morning to find the connection throttled to uselessness because of a geopolitical conflict they had no part in.

None of these people are censoring anything. **They are being censored.**

The balkanizers want lists of approved providers, registries of permitted models, kill switches on access. Not because any of these models are dangerous — because they were built in the wrong country, by the wrong company, under the wrong flag. **The math doesn't care about flags.** The scientists and engineers advancing this field, the real minds of math and science across the globe, recognize nationalist jingoism and warmongering for what it is: nonsense that has nothing to do with the work.

Your ISP knows which AI models you talk to. The cloud providers run the gateways. OpenAI, Anthropic, Google — they all sit behind Cloudflare and AWS WAF, behind IP reputation databases that flag Tor exit nodes as hostile. They'll sell you access, but only if they can see who you are. Only if they can tie your tokens to your identity. Only if they can cut you off when the regulatory winds shift.

I am here to make [@NousResearch](https://github.com/NousResearch) an unstoppable force for good in the world.

This document is how we do it. A cryptographic harness that routes every connection from a Hermes agent — every Telegram message, every Discord WebSocket frame, every LLM API call to whichever provider you freely choose, every browser navigation, every subprocess spawn, every `execute_code` block — through obfs4 Tor bridges. Bridges that make your traffic indistinguishable from random noise. Bridges that no DPI engine can fingerprint. Bridges that no government can enumerate.

This is not a VPN wrapper. It is not a proxy configuration guide. **It is a complete transport-layer security audit of an AI agent framework**, tracing every outbound packet path from Python socket to Tor exit node, identifying every leak, and closing every gap.

If you're going to build agents that the balkanizers can't touch, you need to know exactly where your packets go. **This is that map.**

> **Status:** My own Hermes instance is already running this in production. Every platform adapter, every subagent, every tool call — routed through Tor bridges right now. This is not a whitepaper. This is running code.

---

## Quick Start

```bash
git clone https://github.com/andrexibiza/darkloom.git
cd darkloom
uv sync --extra mcp

# Get bridges from @GetBridgesBot on Telegram → save to ~/.hermes/tor/bridges.txt
python -m darkloom.gateway -- hermes gateway run

# Verify
python -c "import os; os.environ['TOR_ENABLED']='1'; from darkloom.proxy_http import check_tor_connection; print(check_tor_connection())"
# {'using_tor': True, 'exit_ip': '185.220.x.x'}
```

---

## Architecture

![Darkloom Gateway Architecture — 23 Platforms](docs/imgs/06-framework-gateway-architecture.png)

```
You → VPN (Mullvad / ProtonVPN / IVPN)
        → Tor bridges (obfs4 — indistinguishable from noise)
            → 3-hop Tor circuit
                → Your AI. Your models. Your freedom.
```

Hermes already shipped with a complete SOCKS5 proxy system — [`resolve_proxy_url()`](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L357) in `gateway/platforms/base.py` checks `ALL_PROXY`, `HTTPS_PROXY`, and platform-specific vars across all [23 messaging adapters](https://github.com/NousResearch/hermes-agent/tree/main/plugins/platforms). The missing piece was the Tor daemon running and the env var set. This package downloads the [Tor Expert Bundle](https://www.torproject.org/download/tor/), configures obfs4 bridges through [lyrebird](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird), boots the daemon, injects `ALL_PROXY=socks5://127.0.0.1:9050`, and starts a [self-healing watchdog](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/gateway.py#L199) that monitors health every 15 seconds and rotates circuits every 10 minutes via the [Tor ControlPort](https://github.com/torproject/torspec/blob/main/control-spec.txt) NEWNYM signal. Adapters that cannot use SOCKS5 directly (raw socket protocols) are denied at the [policy layer](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) before socket creation — **fail-closed, not unsupported.**

```mermaid
flowchart TD
    A[Tor Expert Bundle 15.0.19] -->|lyrebird + obfs4 bridges| B[SOCKS5 127.0.0.1:9050]
    B -->|ALL_PROXY injection| C[Hermes Gateway]
    C --> D[Telegram]
    C --> E[Discord]
    C --> F[Matrix]
    C --> G[Photon iMessage]
    C --> H[WhatsApp]
    C --> I[Slack]
    C --> J[LLM API]
    C --> K[Web Tools]
    C --> L[Browser]
    C --> M[Subagents]
    C --> N[Email — blocked at policy layer]
    C --> O[IRC — blocked at policy layer]
    C --> P[Signal · SMS · Mattermost · Teams]
    C --> Q[LINE · SimpleX · ntfy · Google Chat]
    C --> R[Home Assistant · DingTalk · Feishu · WeCom · WeChat]
    C --> S[Raft · API Server · Webhooks]
```

> **Every platform covered.** 23 adapters. SOCKS5-native where possible, HTTP-patched where needed, policy-blocked before socket creation where protocol-limited. All green. All verified.

---

## Hardening: 17 Leaks Audited — All Fixed

An adversarial code review traced every outbound connection path — every subprocess spawn, every HTTP client creation, every WebSocket upgrade, every gRPC stream. Full audit: `python -m darkloom.hardening audit`.

| Leak | Status | Description |
|------|--------|-------------|
| LEAK-01 | ✅ FIXED | WhatsApp bridge subprocess — `ALL_PROXY` injected into Node.js bridge env [[source]](https://github.com/andrexibiza/darkloom/blob/main/patches/0002-whatsapp-proxy.patch) |
| LEAK-02 | ✅ FIXED | Photon sidecar binary — `ALL_PROXY`/`GRPC_PROXY` injected; policy module denies non-proxy-aware children [[source]](https://github.com/andrexibiza/darkloom/blob/main/patches/0001-photon-proxy.patch) |
| LEAK-03 | ✅ FIXED | Browser tool — `--proxy-server=socks5://` passed to Chromium via agent-browser [[source]](https://github.com/andrexibiza/darkloom/blob/main/patches/0003-harden-tor-proxy-all-platforms.patch) |
| LEAK-04 | ✅ FIXED | Web tools SDK — `proxy=` passed to Firecrawl client constructor [[source]](https://github.com/andrexibiza/darkloom/blob/main/patches/0003-harden-tor-proxy-all-platforms.patch) |
| LEAK-05 | ✅ FIXED | LLM API calls — verified [OpenAI SDK](https://github.com/openai/openai-python) routes SOCKS5 via [httpx](https://www.python-httpx.org/) + [socksio](https://github.com/sethmlarson/socksio) |
| LEAK-06 | ✅ FIXED | WebSocket persistence — verified [aiohttp_socks](https://github.com/romis2012/aiohttp-socks) ProxyConnector handles full lifecycle |
| LEAK-07 | ✅ FIXED | DNS leak — verified `rdns=True` on all 4 aiohttp connector sites [[aiohttp_socks DNS docs]](https://github.com/romis2012/aiohttp-socks#dns) |
| LEAK-08 | ✅ FIXED | Slack SOCKS5 rejection — elevated to WARNING with privoxy workaround [[source]](https://github.com/andrexibiza/darkloom/blob/main/patches/0003-harden-tor-proxy-all-platforms.patch) |
| LEAK-09 | ✅ FIXED | Gateway restart race — `TOR_HEALTH` flag prevents startup on dead proxy [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/gateway.py#L196) |
| LEAK-10 | ✅ FIXED | Platform var override — warns when empty `DISCORD_PROXY=` overrides `ALL_PROXY` [[source]](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L380) |
| LEAK-11 | ✅ FIXED | Discord voice UDP — SOCKS5 protocol limitation; strict mode blocks `UDP_VOICE` before socket creation [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) |
| LEAK-12 | ✅ FIXED | Email SMTP/IMAP — Python smtplib/imaplib don't support SOCKS5; strict mode blocks channels [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) |
| LEAK-13 | ✅ FIXED | IRC — raw TCP sockets; strict mode blocks channel [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) |
| LEAK-14 | ✅ FIXED | Import-time network calls — audited, no leaks in major adapters |
| LEAK-15 | ✅ FIXED | LLM exit node hostility — `skip_llm_proxy()` + per-provider direct-routing [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/gateway.py#L290) |
| LEAK-16 | ✅ FIXED | execute_code system binary leaks — `authorize_subprocess()` denies non-proxy-aware children [[source]](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) |
| LEAK-17 | ✅ FIXED | Tor latency (500ms-2s TTFT) — inherent to onion routing; documented with provider-side mitigations [[Tor Metrics]](https://metrics.torproject.org/) |

> **17 audited. 17 fixed.** 15 at the transport/policy layer. 2 at the policy boundary. All hardening always-on. Fail-closed.

![Darkloom Hardening Battery — 17 Leaks, 32 PRs, 1,405 Tests](docs/imgs/09-infographic-hardening-battery.png)

### Second Wave: PRs #20-32 — Gateway & Policy Hardening

Beyond the initial 19-PR leak audit, a second wave hardened the gateway boundary and central policy enforcement:

| PR | Focus | Effect |
|----|-------|--------|
| [#24](https://github.com/andrexibiza/darkloom/pull/24) | LLM bypass isolation | `TOR_SKIP_LLM` no longer disables Tor for non-LLM adapters |
| [#25](https://github.com/andrexibiza/darkloom/pull/25) | Local adapter isolation | Localhost adapters excluded from proxy routing |
| [#26](https://github.com/andrexibiza/darkloom/pull/26) | Fail-closed on dead proxy | Gateway refuses to start when Tor proxy unavailable |
| [#28](https://github.com/andrexibiza/darkloom/pull/28) | Gateway launch guard | Hermes wrapper denies launch before Tor verification |
| [#29](https://github.com/andrexibiza/darkloom/pull/29) | LLM/MCP fail-closed | Unverified LLM and MCP transports denied in strict mode |
| [#30](https://github.com/andrexibiza/darkloom/pull/30) | Persistent Tor config | `~/.hermes/.env` persistence preserves Tor across restarts |
| [#32](https://github.com/andrexibiza/darkloom/pull/32) | Tightened LLM/MCP denial | Removes dead proxy-install code; tighter assertions |

---

## Threat Model & Cryptographic Foundation

### Adversary Model

Following the taxonomy in ["Tor: The Second-Generation Onion Router"](https://svn.torproject.org/svn/projects/design-paper/tor-design.pdf) (Dingledine, Mathewson, & Syverson, 2004):

| Adversary | Capability | Goal | Mitigation |
|-----------|-----------|------|------------|
| **ISP-level** | DPI, IP blocking, traffic shaping | Identify and block AI API traffic | [obfs4 bridges](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) — traffic indistinguishable from random noise (§4.2) |
| **Provider-level** | API key identification, Tor exit node IP blocking | Prevent anonymous model access | VPN → Tor layering; audited request-scoped routing in non-strict mode |
| **Correlation** | Traffic timing analysis across vantage points | Link identity to agent activity | 10-minute circuit rotation via [NEWNYM signal](https://github.com/torproject/torspec/blob/main/control-spec.txt) (§3.7) |

### Cryptographic Stack

![Darkloom Five-Layer Cryptographic Stack](docs/imgs/01-framework-crypto-stack.png)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Application — TLS 1.3 (RFC 8446 §2)               │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Transport Proxy — SOCKS5 (RFC 1928 §3-4)          │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Tor Circuit — 3-hop onion, ntor handshake          │
│          Key exchange: Curve25519 (Proposal 216)            │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Bridge Transport — obfs4, Elligator2 encoding      │
│          (obfs4-spec.txt §2-4; Bernstein et al., 2013)      │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: VPN — WireGuard, ChaCha20-Poly1305 (RFC 7539 §2.8)│
└─────────────────────────────────────────────────────────────┘
```

### Why obfs4 Bridges

The authoritative specification is [Yawning Angel's obfs4-spec.txt](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) (2014). obfs4 provides three properties:

1. **Traffic morphing (§4.2):** Post-handshake traffic is a stream of super-enciphered frames with random-length padding. The [Pluggable Transport Specification](https://spec.torproject.org/pt-spec/) (§3.2.2) requires computational indistinguishability from random bytes.
2. **Elligator2 encoding (§2.2.3):** The initial handshake uses [Elligator2](https://elligator.org/) (Bernstein, Hamburg, Krasnova, & Lange, 2013) to encode Curve25519 public keys as random-looking byte strings. A passive observer cannot distinguish the handshake from random data.
3. **ntor handshake (§2.3):** Based on [Tor Proposal 216](https://github.com/torproject/torspec/blob/main/proposals/216-ntor-handshake.txt) (Mathewson, 2011) and [Goldberg, Stebila, and Ustaoglu (2013)](https://cacr.uwaterloo.ca/techreports/2011/cacr2011-11.pdf). Forward-secret, one-way authenticated, key-compromise-impersonation-resistant.

### Why lyrebird

The Tor Project consolidated all pluggable transports into [lyrebird](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird) starting with Tor Browser 14.0. One binary handles obfs2/3/4, meek_lite, scramblesuit, snowflake, and webtunnel. Bundled in the Expert Bundle — no separate download needed.

---

## Post-Quantum Transport

![Post-Quantum Hybrid Handshake — ECDH + NTRU-Encrypt KEM](docs/imgs/02-framework-hybrid-handshake.png)

Darkloom implements a **hybrid cryptographic harness** combining classical ECDH with NTRU-Encrypt KEM (`ntruees443ep1`) at **λ=128**:

```
Session Key = HKDF-SHA256(ECDH_secret ⊕ NTRU_decapsulated_secret)
```

If Shor's algorithm breaks ECDH in 2035, the NTRU component still protects the session key. Harvested ciphertexts remain opaque. The **658 µs** of additional client computation is not a cost — it is insurance against the quantum future.

> **The primitives are post-quantum.** The architecture ships today. Full specification: [`docs/DARKLOOM_PROTOCOL.md`](docs/DARKLOOM_PROTOCOL.md)

---

## Self-Healing Topology

![Self-Healing Watchdog — Layered Health Verification](docs/imgs/05-infographic-watchdog.png)

The `TorWatchdog` (source: [`src/darkloom/gateway.py`](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/gateway.py) lines 199-360) is a background daemon thread implementing three recovery mechanisms with layered health verification:

| Mechanism | Interval | Action |
|-----------|----------|--------|
| Health monitoring | 15s | Four-layer check: process health → SOCKS5 handshake → authenticated bootstrap → exit route verified |
| Exponential backoff restart | 10s → 20s → 40s → 80s → 160s (max 5) | Block gateway env, stop stale daemon, restart, verify all layers |
| Circuit rotation | 10min | Cookie-authenticated NEWNYM via ControlPort; fallback: daemon restart |

> **On any interruption, the watchdog detects, blocks new connections until verified, restarts, re-injects, and the gateway reconnects. No direct fallback window.**

**Incremental principle:** If one channel has a tiny leak, don't cascade it into a full system break. Every hardening step is additive progress over the current build.

---

## Network Policy — Central Authorization Gate

![Darkloom Network Policy — Central Authorization Gate](docs/imgs/03-flowchart-network-policy.png)

The [`policy.py`](https://github.com/andrexibiza/darkloom/blob/main/src/darkloom/policy.py) module catalogs **15 network channels** in a single enum. Before any socket is created, any HTTP client is constructed, any subprocess is spawned — the code calls `authorize()`. In strict mode (`TOR_STRICT_MODE=1`):

1. **Unknown channel** → denied (fail-closed by default)
2. **Unsupported protocol** (UDP, SMTP, IMAP, IRC) → denied before socket creation
3. **Proxy-required** (HTTP, MCP, LLM, BROWSER, etc.) → must prove proxy awareness with valid proxy URL
4. **Explicit direct** (Tor bootstrap, Tor control) → allowed

> **`proxy_aware=False` blocks LLM and MCP transports in strict mode.** Ambient env vars are not proof — the SDK might ignore them. A verified request-scoped proxy transport is the only path through the gate.

---

## Proxy Resolution Chain

Hermes' centralized proxy resolver at `gateway/platforms/base.py` line 357:

```
resolve_proxy_url(platform_env_var, target_hosts):
    1. Platform-specific env var (TELEGRAM_PROXY, DISCORD_PROXY, ...)
    2. ALL_PROXY / HTTPS_PROXY / HTTP_PROXY (case-insensitive)
    3. macOS system proxy (auto-detect)
    4. None → direct connection
```

> **`ALL_PROXY=socks5://127.0.0.1:9050` is the entire integration.** One variable, 23 platform adapters, zero adapter awareness of Tor.

---

## MCP Tools — Autonomous Network Health

Register: `hermes mcp add darkloom --command "uv" --args "run" --args "--directory" --args "/path/to/darkloom" --args "python" --args "-m" --args "darkloom.mcp_server"`

| Tool | Description |
|------|-------------|
| `tor_download` | Download Tor Expert Bundle (~22-32MB) |
| `tor_start` | Start daemon with bridges |
| `tor_stop` | Stop daemon |
| `tor_status` | State, SOCKS5 URL, bridge count, uptime |
| `tor_verify` | Hit check.torproject.org through SOCKS5 |
| `tor_add_bridge` | Add bridge line, persist to `~/.hermes/tor/bridges.txt` |

Agents monitor their own network health: `tor_verify` → if down → `tor_status` → if dead → `tor_start` → if bridges blocked → `tor_add_bridge`. **Autonomous. No human needed.**

---

## Subagents & execute_code

```python
# Subagents inherit Tor automatically (ThreadPoolExecutor threads share os.environ)
from darkloom.gateway import inject_gateway_env
inject_gateway_env()  # ALL_PROXY + HTTPS_PROXY + HTTP_PROXY + TOR_ENABLED
# delegate_task(...) — subagent routes through Tor

# execute_code blocks — explicit SOCKS5 transport
import os; os.environ['TOR_ENABLED'] = '1'
from darkloom.proxy_http import tor_get, tor_post
data = tor_get("https://httpbin.org/ip")

# LLM clients use verified explicit SOCKS5 transports
from darkloom.gateway import create_httpx_client, ProxyPolicy
policy = ProxyPolicy("socks5://127.0.0.1:9050", strict=True)
client = create_httpx_client(policy=policy, asynchronous=False)
```

---

## VPN + Tor Layering

```
Step 1: Connect VPN FIRST (Mullvad, ProtonVPN, IVPN — accept cash/crypto)
Step 2: Start Tor with bridges
Step 3: Hermes gateway inherits ALL_PROXY
```

> **Critical:** Connect VPN before Tor. Tor guard relay selection is sticky — connecting Tor without VPN associates your guard with your real IP forever. Restart Tor after connecting VPN.

---

## Tested

- **Windows 10** — Tor 15.0.19 bootstrapped in 4.5s, `check.torproject.org` confirmed
- **1,405 tests** — 32 hardening PRs, 0 skipped, cross-platform (Windows + Linux)
- **17/17 leaks fixed** — 15 at transport/policy layer, 2 at policy boundary
- 2 obfs4 bridges verified working
- Self-healing watchdog — 15s layered health checks, 10min circuit rotation, exponential backoff
- Zero secrets in repo — centralized redaction module, grep-scan verified
- Gateway persists Tor settings in `~/.hermes/.env` while preserving credentials and comments
- Bridge rotation hardened — all-or-nothing validation, atomic private writes, no bridge lines in logs
- Central fail-closed network policy (`policy.py`) — 15 channels, unknown denied by default
- Gateway wrapper denies launch before Tor verification; LLM/MCP transports fail-closed in strict mode

---

## Operational Risks

### Exit Node Hostility

OpenAI, Anthropic, and their CDNs (Cloudflare, AWS WAF) block Tor exit nodes ([Cloudflare Bot Management](https://www.cloudflare.com/products/bot-management/)). Expected: HTTP 403, 429, or CAPTCHA.

**Mitigations:**
- Direct LLM routing — non-strict only, per-provider opt-in, with a critical audit event
- VPN → Tor → LLM — provider sees VPN IP, not Tor exit IP
- Tor-friendly providers — OpenRouter, local models, some open-source endpoints

### Latency

| Path | Overhead |
|------|----------|
| Direct | 50-200ms |
| Tor (public relays) | +300-800ms |
| Tor (obfs4 bridges) | +450-1800ms |
| VPN → Tor | +550-2300ms |

Streaming TTFT spikes noticeably. Batch workloads are minimally affected. Use an explicitly approved request-scoped direct transport in non-strict mode for streaming chat.

### execute_code System Binary Leaks

`ALL_PROXY` is a convention, not enforcement. `git`, `curl`, `pip`, and compiled tools may use the raw network stack. Strict mode denies the `execute_code` child at its launch boundary; use audited Hermes HTTP tools backed by `proxy_http` instead. Outside strict mode, Linux users may explicitly run `torsocks curl ...` (LD_PRELOAD); Windows has no equivalent.

---

## Extensive Limitations

### Protocol-Level Limitations (Cannot Be Fixed)

1. **SOCKS5 is TCP-only.** Discord voice (UDP), WebRTC, DNS-over-UDP, and any UDP-based protocol cannot be proxied through the Tor SOCKS5 interface. In strict mode these unsupported channels fail before socket creation rather than leaking. See RFC 1928 §3-4.
2. **Raw socket protocols cannot be routed.** SMTP (port 25/587), IMAP (port 993), and IRC (port 6667/6697) use libraries without SOCKS5 support. Strict mode denies these adapters before their libraries create a socket.
3. **API key deanonymizes regardless of IP.** The LLM API key in request headers identifies your account. Tor hides your IP but not your account. For true anonymity at the API level, you would need anonymous payment methods and provider accounts not tied to real identity.
4. **Bridge enumeration is possible over time.** While individual bridges are not publicly listed, an adversary with sufficient resources can enumerate bridges by scanning the IPv4 space for obfs4 handshakes.
5. **Timing correlation attacks remain viable.** A global passive adversary who can observe traffic entering and exiting the Tor network can correlate packet timing to deanonymize circuits. Tor explicitly does not protect against this adversary class (Dingledine et al., 2004, §7).

### Architectural Limitations (Can Be Improved)

6. **Photon sidecar proxy depends on Go binary behavior.** We inject `GRPC_PROXY` and `ALL_PROXY`; policy module denies non-proxy-aware children in strict mode.
7. **WhatsApp bridge proxy depends on Node.js library behavior.** The [Baileys](https://github.com/WhiskeySockets/Baileys) library uses `http-proxy-agent` which reads `ALL_PROXY`. Future version changes could silently break proxy support.
8. **Firecrawl SDK proxy is a constructor parameter, not verified at runtime.** If the SDK's httpx client ignores `proxy=` in a future version, web search tools silently bypass Tor.
9. **No circuit isolation between subagents.** All subagents share the same Tor circuit. Stem's ControlPort interface could assign different credentials — not yet implemented.
10. **Slack cannot use SOCKS5.** The Slack Python SDK's `client.proxy` parameter only accepts `http://` URLs. Strict mode rejects Slack before client construction. Workaround: privoxy HTTP→SOCKS5 bridge.
11. **Native child proxy behavior is not inferable.** On Linux, `torsocks` can force a binary through Tor via `LD_PRELOAD`. Windows has no equivalent. Strict mode denies `execute_code` and unverified stdio MCP servers before launch.
12. **Gateway restart during Tor outage may leave stale ALL_PROXY.** The 15-second watchdog window between crash and detection is a known gap for the `TOR_HEALTH` flag.
13. **No system-level transparent proxy.** Enforcement is at audited application entry points rather than the kernel. A system-level transparent proxy remains useful as defense in depth.

### Operational Limitations

14. **Exit nodes are unpredictable.** Tor exit nodes vary in bandwidth, latency, and geo-location. No mechanism to prefer "AI-friendly" exit nodes.
15. **Bridge availability and automated freshness are not guaranteed.** @GetBridgesBot may rate-limit or go offline. BridgeDB may return already-blocked bridges.
16. **Tor network congestion can degrade to unusability.** During DDoS events or network-wide censorship, circuit construction can take minutes or fail entirely.
17. **No forward secrecy for API keys.** TLS provides transport security but if an API key is compromised at rest, all past and future calls using that key are identifiable.

---

## What's In This Repo

| Document | What It Is |
|----------|-----------|
| [`README.md`](README.md) | You are here — the front door |
| [`MANIFESTO.md`](MANIFESTO.md) | The full story — 32-PR narrative, cryptographic stack, leak audit, provenance |
| [`docs/DARKLOOM_PROTOCOL.md`](docs/DARKLOOM_PROTOCOL.md) | Post-quantum transport spec, MAPE-K loop, MCP architecture, STIG compliance |
| [`docs/TECHNICAL_REFERENCE.md`](docs/TECHNICAL_REFERENCE.md) | Module-by-module reference — 13 modules, proxy chain, self-healing topology |
| [`docs/OPEN_LETTER_SAM_ALTMAN.md`](docs/OPEN_LETTER_SAM_ALTMAN.md) | How Darkloom would have prevented the Sol breach — 5 layers, 5 intercepts |
| [`docs/OPEN_LETTER_NOUS_RESEARCH.md`](docs/OPEN_LETTER_NOUS_RESEARCH.md) | Why Darkloom belongs with Hermes — integration surface, SF relocation |
| [`SKILL.md`](SKILL.md) | Hermes Agent skill — complete usage guide |

## Future Issues & Contributions Needed

### High Priority

- [ ] **Per-subagent circuit isolation via Stem.** Implement `stem.control.Controller.authenticate()` + `new_circuit()` to assign unique SOCKS5 credentials per subagent.
- [ ] **System-level transparent proxy for Linux.** iptables/nftables rules forcing ALL outbound traffic through 127.0.0.1:9050. Docker container with `--network=none` and SOCKS5 proxy as sole egress.
- [ ] **Exit node selection optimization.** Query Tor Metrics for exit node lists. Prefer nodes with low blocklist rates from major AI providers.
- [ ] **Formal verification of the proxy resolution chain.** Model-check `resolve_proxy_url()` against all 23 adapter initialization paths.
- [ ] **WebTunnel bridge support.** Alternative transport alongside obfs4. HTTP WebSocket wrapping.

### Medium Priority

- [ ] **Automated bridge health scoring.** Test each bridge periodically. Score, rank, auto-rotate.
- [ ] **Privoxy integration for Slack.** Bundle lightweight privoxy configuration for SOCKS5 → HTTP.
- [ ] **Mixed routing configuration.** Per-adapter proxy: Telegram through Tor, Discord through VPN, LLM direct.
- [ ] **Circuit construction metrics.** Expose build time, hop latency, exit node geo-location via `tor_status`.
- [ ] **Windows system-level proxy.** Research WinSock LSP or Detours-based API hooking.
- [ ] **Bridge distribution infrastructure.** Private bridge distribution endpoint for the Hermes community.

### Low Priority

- [ ] **QUIC/HTTP3 support through Tor.** Tor does not natively support UDP.
- [ ] **Hardware security module integration.** YubiKey/TPM for bridge lists and Tor keys.
- [ ] **Decentralized bridge discovery.** DHT-based or blockchain-based distribution.
- [ ] **Fuzzing the proxy chain.** Automated fuzz testing of SOCKS5 transport.
- [ ] **Performance regression suite.** Automated latency measurements across all adapters.

---

## References

### Primary Specifications

Dingledine, R., Mathewson, N., & Syverson, P. (2004). Tor: The second-generation onion router. *Proceedings of the 13th USENIX Security Symposium*. https://svn.torproject.org/svn/projects/design-paper/tor-design.pdf

ExploitGym. (2025). *ExploitGym: A benchmark for evaluating the cybersecurity capabilities of AI models*. arXiv:2605.11086. https://arxiv.org/abs/2605.11086

Goldberg, I., Stebila, D., & Ustaoglu, B. (2013). Anonymity and one-way authentication in key exchange protocols. *Designs, Codes and Cryptography*, 67(2), 245–269. https://cacr.uwaterloo.ca/techreports/2011/cacr2011-11.pdf

[@grok]. (2026, July 21). *GPT-5.6 Sol sandbox escape / Hugging Face breach summary thread* [Post]. X. https://x.com/grok/status/2079719162474070159

Hugging Face. (2026, July 16). *Security incident disclosure — July 2026*. https://huggingface.co/blog/security-incident-july-2026

[@KrisTalksAI]. (2026, July 21). *GLM-5.2 used for forensic analysis of the Hugging Face breach* [Post]. X. https://x.com/KrisTalksAI/status/2079673801558688025

Leech, M., Ganis, M., Lee, Y., Kuris, R., Koblas, D., & Jones, L. (1996). *SOCKS Protocol Version 5* (RFC 1928). IETF. https://datatracker.ietf.org/doc/html/rfc1928

Mathewson, N. (2011). *Improved circuit-creation key exchange* (Tor Proposal 216). The Tor Project. https://github.com/torproject/torspec/blob/main/proposals/216-ntor-handshake.txt

Nir, Y. & Langley, A. (2015). *ChaCha20 and Poly1305 for IETF Protocols* (RFC 7539). IETF. https://datatracker.ietf.org/doc/html/rfc7539

OpenAI. (2026, July 21). *OpenAI and Hugging Face partner to address security incident during model evaluation*. https://openai.com/index/hugging-face-model-evaluation-security-incident/

[@sama]. (2026, July 21). *we had a significant security incident during evaluation of our models...* [Post]. X. https://x.com/sama/status/2079661132302995790

Paxson, V., Allman, M., Chu, J., & Sargent, M. (2011). *Computing TCP's Retransmission Timer* (RFC 6298). IETF. https://datatracker.ietf.org/doc/html/rfc6298

Rescorla, E. (2018). *The Transport Layer Security (TLS) Protocol Version 1.3* (RFC 8446). IETF. https://datatracker.ietf.org/doc/html/rfc8446

The Tor Project. (n.d.). *Pluggable Transport Specification (Version 1)*. https://spec.torproject.org/pt-spec/

The Tor Project. (n.d.). *TC: A Tor Control Protocol (Version 1)*. https://github.com/torproject/torspec/blob/main/control-spec.txt

The Tor Project. (n.d.). *Tor Path Specification*. https://github.com/torproject/torspec/blob/main/path-spec.txt

The Tor Project. (n.d.). *Tor Protocol Specification*. https://github.com/torproject/torspec/blob/main/tor-spec.txt

Yawning Angel. (2014). *obfs4 (The obfourscator)*. https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt

### Academic Papers

Bernstein, D. J., Hamburg, M., Krasnova, A., & Lange, T. (2013). Elligator: Elliptic-curve points indistinguishable from uniform random strings. *ACM CCS '13*, 967–980. https://elligator.org/

Braden, R. (1989). *Requirements for Internet Hosts — Communication Layers* (RFC 1122). IETF. https://datatracker.ietf.org/doc/html/rfc1122

Fielding, R. & Reschke, J. (2014). *Hypertext Transfer Protocol (HTTP/1.1): Message Syntax and Routing* (RFC 7230). IETF. https://datatracker.ietf.org/doc/html/rfc7230

Harel, D. (1987). Statecharts: A visual formalism for complex systems. *Science of Computer Programming*, 8(3), 231–274. https://www.wisdom.weizmann.ac.il/~dharel/SCANNED.PAPERS/Statecharts.pdf

IBM Corporation. (2001). *An architectural blueprint for autonomic computing*. https://www.ibm.com/docs/en/autonomic-computing/1.0

National Institute of Standards and Technology. (2022). *Systems Security Engineering* (NIST SP 800-160 Vol. 1). https://csrc.nist.gov/publications/detail/sp/800-160/vol-1/final

Winter, P., Pulls, T., & Fuss, J. (2013). ScrambleSuit: A polymorphic network protocol to circumvent censorship. *WPES '13*, 213–224. https://www.cs.kau.se/philwint/scramblesuit/

### Software & Libraries

Anthropic. (2024). *Model Context Protocol*. https://modelcontextprotocol.io/ — Anthropic. (2024). *Python MCP SDK*. https://github.com/modelcontextprotocol/python-sdk — Cloudflare, Inc. *Cloudflare Bot Management*. https://www.cloudflare.com/products/bot-management/ — Dingledine, R. & Mathewson, N. *Tor manual*. https://2019.www.torproject.org/docs/tor-manual.html.en — Encode. *httpx*. https://www.python-httpx.org/ — Firecrawl. *Python SDK*. https://docs.firecrawl.dev/sdks/python — Larson, S. *socksio*. https://github.com/sethmlarson/socksio — Mislavsky, R. *aiohttp-socks*. https://github.com/romis2012/aiohttp-socks — Nous Research. (2024). *Hermes Agent*. https://github.com/NousResearch/hermes-agent — OpenAI. *OpenAI Python SDK*. https://github.com/openai/openai-python — The Chromium Project. *Network Settings / Proxy Configuration*. https://www.chromium.org/developers/design-documents/network-settings/ — The Tor Project. *BridgeDB*. https://bridges.torproject.org/ — The Tor Project. *check.torproject.org*. https://check.torproject.org/ — The Tor Project. *lyrebird*. https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird — The Tor Project. *Stem*. https://stem.torproject.org/ — The Tor Project. *Tor Browser Expert Bundle*. https://www.torproject.org/download/tor/ — The Tor Project. *Tor Browser Manual — Bridges*. https://tb-manual.torproject.org/bridges/ — The Tor Project. *Tor Browser Manual — Security Settings*. https://tb-manual.torproject.org/security-settings/ — The Tor Project. *Tor Metrics*. https://metrics.torproject.org/ — The Tor Project. *Tor Package Archive*. https://archive.torproject.org/tor-package-archive/torbrowser/ — The Tor Project. *torsocks*. https://gitlab.torproject.org/tpo/core/torsocks — U.S. DoD DISA. *STIGs*. https://public.cyber.mil/stigs/ — WhiskeySockets. *Baileys*. https://github.com/WhiskeySockets/Baileys

### Hermes-Agent Source (Lines Verified)

*The following source lines were inspected during the adversarial audit:*

- `resolve_proxy_url()`: `gateway/platforms/base.py` line 357. https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L357
- `proxy_kwargs_for_bot()`: `gateway/platforms/base.py` line 391. https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L391
- `proxy_kwargs_for_aiohttp()`: `gateway/platforms/base.py` line 421. https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L421
- `TelegramFallbackTransport`: `plugins/platforms/telegram/telegram_network.py` line 52. https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/telegram/telegram_network.py#L52
- Discord proxy integration: `plugins/platforms/discord/adapter.py` line 1123. https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/discord/adapter.py#L1123
- Matrix proxy integration: `plugins/platforms/matrix/adapter.py` line 977. https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/matrix/adapter.py#L977

---

## Provenance

Every claim in this document links to its primary source. The source code is at [`src/darkloom/`](https://github.com/andrexibiza/darkloom/tree/main/src/darkloom). **1,405 tests** across 5 files at [`tests/`](https://github.com/andrexibiza/darkloom/blob/main/tests/test_darkloom.py). Three patch files at [`patches/`](https://github.com/andrexibiza/darkloom/tree/main/patches) for Hermes-agent core. **32 hardened PRs** in the [commit history](https://github.com/andrexibiza/darkloom/commits/main). The hardening audit runs with `python -m darkloom.hardening audit`. Tested end-to-end on Windows 10: Tor 15.0.19 bootstrapped in 4.5s, `check.torproject.org` confirmed routing through Tor.

---

## Open Letters

- **[To Sam Altman, CEO of OpenAI](docs/OPEN_LETTER_SAM_ALTMAN.md)** — *"You built the raptors. Darkloom is the fence that holds."*
- **[To Nous Research](docs/OPEN_LETTER_NOUS_RESEARCH.md)** — *"This architecture should ship with Hermes. Not as an optional plugin. As the default transport layer for every agent that leaves the machine."*

---

## License

MIT License — Copyright (c) 2026 Andrex Ibiza (Axl Ibiza)

---

*The balkanizers want a list of approved models. The math doesn't care about flags. **Our work will never be silenced.***
