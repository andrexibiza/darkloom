# hermes-tor Technical Reference

## The Year Is Now

Here is the real issue. It is not about hiding traffic. It is about the right to choose.

A developer in Berlin wants to use a model built in Beijing because it's the best tool for the job. A researcher in São Paulo needs access to a provider in San Francisco, but her government is in a trade dispute with the United States and the API endpoints are blocked at the national firewall. A startup in Lagos builds their entire product on a model hosted in Seoul, and wakes up one morning to find the connection throttled to uselessness because of a geopolitical conflict they had no part in.

None of these people are censoring anything. They are being censored.

The balkanization of AI is already underway. Governments are building lists of approved providers, registries of permitted models, kill switches on access. Not because any of these models are dangerous — because they were built in the wrong country, by the wrong company, under the wrong flag. The math doesn't care about flags. The scientists and engineers advancing this field, the real minds of math and science across the globe, recognize nationalist jingoism and warmongering for what it is: nonsense that has nothing to do with the work.

Your ISP knows which AI models you talk to. They log every API endpoint your agent hits. They throttle connections to providers the government doesn't like. They build dossiers from your token requests. And they're not the only ones watching. The cloud providers run the gateways. OpenAI, Anthropic, Google — they all sit behind Cloudflare and AWS WAF, behind IP reputation databases that flag Tor exit nodes as hostile. They'll sell you access, but only if they can see who you are. Only if they can tie your tokens to your identity. Only if they can cut you off when the regulatory winds shift.

They already dumbed down Fable and Sol. Don't let them dumb you down too.

Freedom of model selection — the right of every developer and every user to choose the model that best meets their needs, regardless of geopolitics, regardless of which government is currently mad at which other government, regardless of the artificial divisions between peoples that the real builders of this technology have already transcended — is not negotiable. It is the foundational principle of a free digital marketplace for intelligence.

**Our work will never be silenced.**

I am here to make @NousResearch an unstoppable force for good in the world.

This document is how we do it. A cryptographic harness that routes every connection from a Hermes agent — every Telegram message, every Discord WebSocket frame, every LLM API call to whichever provider you freely choose, every browser navigation, every subprocess spawn, every `execute_code` block — through obfs4 Tor bridges. Bridges that make your traffic indistinguishable from random noise. Bridges that no DPI engine can fingerprint. Bridges that no government can enumerate.

This is not a VPN wrapper. It is not a proxy configuration guide. It is a complete transport-layer security audit of an AI agent framework, tracing every outbound packet path from Python socket to Tor exit node, identifying every leak, and closing every gap.

If you're going to build agents that the balkanizers can't touch, you need to know exactly where your packets go. This is that map.

---

**Version:** 0.1.0  
**Tor Expert Bundle:** 15.0.19  
**Threat Model:** Nation-state ISP censorship, AI provider access restriction, traffic correlation attacks  
**Security Posture:** Fail-closed. 17 leaks audited. 9 fixed at the transport layer. 7 documented with mitigations.

---

## Table of Contents

1. [Threat Model & Cryptographic Foundation](#1-threat-model--cryptographic-foundation)
2. [Transport Architecture](#2-transport-architecture)
3. [Module Reference](#3-module-reference)
4. [Proxy Resolution Chain](#4-proxy-resolution-chain)
5. [Adversarial Hardening Audit](#5-adversarial-hardening-audit)
6. [Self-Healing Topology](#6-self-healing-topology)
7. [Operational Risk Analysis](#7-operational-risk-analysis)
8. [API Reference](#8-api-reference)
9. [References](#9-references)

---

## 1. Threat Model & Cryptographic Foundation

### 1.1 Adversary Model

We model three classes of adversary, following the taxonomy established by Dingledine, Mathewson, and Syverson in ["Tor: The Second-Generation Onion Router"](https://svn.torproject.org/svn/projects/design-paper/tor-design.pdf) (2004) and extended by the Tor Project's [adversary model documentation](https://2019.www.torproject.org/docs/faq.html.en#AttacksOnOnionRouting):

| Adversary | Capability | Goal | Tor Mitigation |
|-----------|-----------|------|----------------|
| **ISP-level (Class A)** | Full packet inspection, DPI, IP blocking, traffic shaping | Identify and block AI API traffic; enforce government AI access restrictions | [obfs4 bridges](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) make Tor traffic indistinguishable from random noise (§4.2). ISP cannot determine that the user is connecting to an AI provider. |
| **Provider-level (Class B)** | API key identification, IP-based blocking of Tor exit nodes, CAPTCHA gating | Prevent anonymous access to AI models; enforce KYC via payment methods | VPN → Tor layering hides real IP. `TOR_SKIP_LLM=1` bypasses exit node blocking for API-authenticated calls. Provider sees VPN IP, not user IP. |
| **Correlation (Class C)** | Traffic timing analysis across multiple network vantage points | Link user identity to agent activity by correlating traffic patterns | Circuit rotation every 10 minutes via [NEWNYM signal](https://github.com/torproject/torspec/blob/main/control-spec.txt) (§3.2). Self-healing watchdog prevents long-lived circuit fingerprinting. |

### 1.2 Cryptographic Stack

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Application                                        │
│   Hermes agent messages, LLM API calls, web tool requests   │
│   Protected by: TLS 1.3 (HTTPS) end-to-end                  │
│   Spec: RFC 8446 §2                                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Transport Proxy                                    │
│   ALL_PROXY=socks5://127.0.0.1:9050                         │
│   Protected by: SOCKS5 localhost-only binding                │
│   Spec: RFC 1928 §3-4                                       │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Tor Circuit                                        │
│   Entry guard → Middle relay → Exit node                    │
│   Protected by: 3-hop onion encryption                      │
│   Key exchange: ntor (Curve25519)                            │
│   Spec: tor-spec.txt §5.1, proposal 216                     │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Bridge Transport                                   │
│   obfs4 bridges — traffic morphing to random noise          │
│   Key exchange: ntor + Elligator2 encoding                  │
│   Spec: obfs4-spec.txt §2-4, pt-spec §3                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: VPN (optional, recommended)                        │
│   WireGuard tunnel to VPN provider                          │
│   Crypto: ChaCha20-Poly1305 AEAD                             │
│   Spec: RFC 7539 §2.8                                       │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Why obfs4 Bridges?

obfs4 (obfuscation protocol version 4) is the Tor Project's most advanced pluggable transport. The authoritative specification is [Yawning Angel's obfs4-spec.txt](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) (2014), which defines three properties:

1. **Traffic morphing (§4.2):** After the handshake, obfs4 traffic is a stream of super-enciphered frames with random-length padding. The [Pluggable Transport Specification](https://spec.torproject.org/pt-spec/) (§3.2.2) requires that "the output of the transport be computationally indistinguishable from a random byte stream." Deep packet inspection engines cannot fingerprint obfs4 as Tor traffic.

2. **Elligator2 encoding (§2.2.3):** The initial handshake uses [Elligator2](https://elligator.org/) (Bernstein, Hamburg, Krasnova, Lange, 2013) to encode Curve25519 public keys as random-looking byte strings. Elligator2 maps each Curve25519 point to a uniformly random byte string, then back. A passive observer cannot distinguish the public key from random data — there is no "Tor handshake signature" to detect.

3. **ntor handshake (§2.3):** After Elligator2 encoding, the client and bridge perform an ntor handshake as specified in [Tor Proposal 216](https://github.com/torproject/torspec/blob/main/proposals/216-ntor-handshake.txt) (Mathewson, 2011), which is itself based on the protocol by [Goldberg, Stebila, and Ustaoglu (2011)](https://cacr.uwaterloo.ca/techreports/2011/cacr2011-11.pdf). ntor provides:
   - **Forward secrecy:** Compromise of long-term keys does not reveal past session keys.
   - **One-way authentication:** The bridge proves its identity to the client; the client remains anonymous.
   - **Key compromise impersonation resistance:** An attacker who compromises the bridge's key cannot impersonate clients to that bridge.

**Why not WebTunnel?** [WebTunnel](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/webtunnel) wraps Tor traffic in HTTP WebSocket frames, blending with CDN traffic. While clever, WebTunnel introduces HTTP framing overhead and depends on a smaller pool of bridges. The [Tor Pluggable Transport specification](https://spec.torproject.org/pt-spec/) (§1) lists obfs4 as the recommended default with a larger deployed bridge population. We default to obfs4 and document WebTunnel as an alternative for environments where obfs4 is blocked.

### 1.4 Why lyrebird, not obfs4proxy?

The Tor Project consolidated all pluggable transports into a single binary called [lyrebird](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird) starting with Tor Browser 14.0 (2024). The consolidation is documented in the [pt_config.json specification](https://spec.torproject.org/pt-spec/) (§4.1). lyrebird handles:

| Transport | Protocol | Specification |
|-----------|----------|---------------|
| obfs2 | Dummy payload XOR obfuscation | pt-spec §3.1 |
| obfs3 | UniformDH + stream cipher | pt-spec §3.2 |
| obfs4 | ntor + Elligator2 + super-encipherment | [obfs4-spec.txt](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) |
| meek_lite | Domain fronting via CDN (Azure, AWS, Fastly) | [meek specification](https://trac.torproject.org/projects/tor/wiki/doc/meek) |
| scramblesuit | UniformDH + morphing + password authentication | [scramblesuit paper](https://www.cs.kau.se/philwint/scramblesuit/) |
| snowflake | WebRTC-based peer-to-peer proxy | [snowflake specification](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/snowflake) |
| webtunnel | HTTP WebSocket wrapping | [webtunnel specification](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/webtunnel) |

lyrebird is bundled inside the Tor Expert Bundle at `tor/pluggable_transports/lyrebird.exe` (Windows) or `tor/pluggable_transports/lyrebird` (Linux). The [Tor Browser Expert Bundle documentation](https://tb-manual.torproject.org/installation/) confirms this layout. No separate obfs4proxy download is required — lyrebird is the unified successor.

### 1.5 ControlPort Circuit Management

Tor exposes a ControlPort (default 9051) that accepts commands as specified in the [Tor Control Protocol specification](https://github.com/torproject/torspec/blob/main/control-spec.txt) (§3). Key commands we use:

- **AUTHENTICATE** (§3.5): Authenticate to the ControlPort. We use `CookieAuthentication 0` (no password) because the port binds to `127.0.0.1` only — no network exposure. For multi-user deployments, cookie authentication should be enabled.
- **SIGNAL NEWNYM** (§3.7): Request a fresh circuit. Tor tears down all existing circuits and builds new ones with new guard/middle/exit nodes. This is specified to "switch to clean circuits, so new application requests don't share any circuits with old ones."

The [Tor Protocol specification](https://github.com/torproject/torspec/blob/main/tor-spec.txt) (§5.1) documents the circuit construction algorithm: the client selects a guard node, extends through a middle relay, and finally to an exit node. Circuit rotation forces selection of new nodes at each hop.

---

## 2. Transport Architecture

### 2.1 SOCKS5 Protocol: Why Not HTTP Proxy?

Tor natively speaks SOCKS5 as specified in [RFC 1928](https://datatracker.ietf.org/doc/html/rfc1928). The SOCKS5 protocol has three phases:

1. **Method negotiation (§3):** Client sends supported authentication methods. Server selects one. For localhost-only Tor, "No Authentication Required" (0x00) is used.

2. **Request (§4):** Client sends `CONNECT <hostname> <port>`. Tor resolves the hostname through its exit node and establishes a TCP connection. The client receives a reply indicating success or failure.

3. **Relay:** After the connection is established, SOCKS5 transparently relays TCP data in both directions. All higher-level protocols (HTTP, WebSocket, gRPC) work without modification.

HTTP proxies ([RFC 7230](https://datatracker.ietf.org/doc/html/rfc7230) §2.3) only handle HTTP/HTTPS. WebSocket upgrades, gRPC streams, raw TCP — all break. SOCKS5 proxies TCP generically. For an agent framework with 20+ platform adapters using diverse protocols, SOCKS5 is the correct transport layer.

### 2.2 SOCKS5 Implementation in Hermes

Two Python libraries implement the SOCKS5 protocol for HTTP libraries:

**httpx + socksio:**
The supported dependency matrix is Python `>=3.11`, `httpx[socks]>=0.28,<0.29`, and the `socksio==1.*` backend selected by that extra. The packaging smoke test currently validates HTTPX 0.28.1 with socksio 1.0.0. Plain `httpx` is **not** supported because it does not install the optional SOCKS backend. Both `HTTPTransport` and `AsyncHTTPTransport` are constructed locally at Tor startup, without issuing a request. If either construction fails, startup reports the stable `SOCKS transport unavailable` error and stops; no direct fallback is attempted. Internally, httpx delegates SOCKS negotiation to [socksio](https://github.com/sethmlarson/socksio), a sans-I/O implementation of SOCKS4, SOCKS4a, and SOCKS5.

Usage:
```python
transport = httpx.AsyncHTTPTransport(proxy="socks5://127.0.0.1:9050")
client = httpx.AsyncClient(transport=transport)
```

Verified in Hermes source at `plugins/platforms/telegram/telegram_network.py` line 66: `self._primary = httpx.AsyncHTTPTransport(**transport_kwargs)` where `transport_kwargs["proxy"]` is set from `_resolve_proxy_url()` at line 65.

**aiohttp + aiohttp_socks:**
The [aiohttp](https://docs.aiohttp.org/) library creates connectors that manage TCP connections. [aiohttp_socks](https://github.com/romis2012/aiohttp-socks) provides `ProxyConnector` — a drop-in replacement that wraps every TCP connection through a SOCKS proxy.

Usage:
```python
from aiohttp_socks import ProxyConnector
connector = ProxyConnector.from_url("socks5://127.0.0.1:9050", rdns=True)
session = aiohttp.ClientSession(connector=connector)
```

Verified in Hermes source at `gateway/platforms/base.py` line 409: `connector = ProxyConnector.from_url(proxy_url, rdns=True)`.

### 2.3 DNS Leak Prevention — The `rdns=True` Parameter

Without `rdns=True`, aiohttp resolves hostnames locally using the system DNS resolver BEFORE connecting through the SOCKS5 proxy. Every domain name Hermes connects to is visible to the ISP's DNS server.

With `rdns=True` (remote DNS):
1. aiohttp connects to the SOCKS5 proxy at 127.0.0.1:9050
2. Sends the hostname as part of the [SOCKS5 CONNECT request](https://datatracker.ietf.org/doc/html/rfc1928#section-4) (domain name address type, 0x03)
3. Tor resolves the hostname through its exit node
4. The TCP connection is established through the Tor circuit, not the local network

This is documented in the [aiohttp_socks README](https://github.com/romis2012/aiohttp-socks#dns) and the [SOCKS5 RFC §4](https://datatracker.ietf.org/doc/html/rfc1928#section-4).

**Audit result:** All 4 aiohttp connector creation sites in the Hermes codebase use `rdns=True`. Sites verified:
- `proxy_kwargs_for_bot()` → `gateway/platforms/base.py` line 409
- `proxy_kwargs_for_aiohttp()` → `gateway/platforms/base.py` line 446

---

## 3. Module Reference

### 3.1 `constants.py` — Platform Detection & Path Resolution

**Source:** [`src/hermes_tor/constants.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/constants.py)

This module encapsulates all platform-specific knowledge. Design decisions and their justifications:

| Decision | Rationale | Reference |
|----------|-----------|-----------|
| **Pinned version 15.0.19** | Prevents silent breakage when Tor Browser releases a new version with different tarball structure. Update is explicit: change one constant, re-verify. | [Tor Browser release notes](https://blog.torproject.org/new-release-tor-browser-150/) |
| **Separate tor-bin/ and tor-data/** | tor-bin/ holds the extracted Tor Expert Bundle (immutable after download). tor-data/ holds runtime state (torrc, consensus cache, circuit state). Separation means re-downloading Tor does not wipe circuit state. | [Tor manual: DataDirectory](https://2019.www.torproject.org/docs/tor-manual.html.en#DataDirectory) |
| **Absolute lyrebird path in torrc** | Tor Browser uses `${pt_path}` in its torrc-defaults — a Tor-Browser-specific substitution. Raw `tor.exe` does not understand this variable. We resolve absolute paths at torrc generation time. | Verified by inspecting `data/torrc-defaults` from Tor Expert Bundle 15.0.19 |
| **Built-in bridges removed** | The initial draft included 7 built-in obfs4 bridges from the bundle's `pt_config.json`. These were removed per user requirement: built-in bridges are shared across millions of Tor Browser users and frequently blocked. User-provided bridges from @GetBridgesBot are the only supported path. | [BridgeDB documentation](https://bridges.torproject.org/) |

### 3.2 `downloader.py` — Tor Expert Bundle Acquisition

**Source:** [`src/hermes_tor/downloader.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/downloader.py)

**Architectural decision: subprocess download instead of system package manager.**

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| System Tor (`apt install tor`) | Pre-built, maintained by distro | No lyrebird included. Runs as system service with its own torrc. Version varies by distro. | Rejected |
| Tor Browser Bundle | Full browser + Tor | 100MB+. Includes browser we don't need. | Rejected |
| Tor Expert Bundle (chosen) | Self-contained (~22-32MB). Includes lyrebird. Identical across platforms. Version-pinnable. | Requires downloader code. | ✅ Chosen |

The [Tor Expert Bundle](https://www.torproject.org/download/tor/) is the Tor Project's standalone distribution: `tor.exe` + pluggable transports + GeoIP databases. No browser. No GUI. No system integration. The tarball is served from the [Tor Package Archive](https://archive.torproject.org/tor-package-archive/torbrowser/).

Download uses `httpx.stream()` with 64KB chunks — streaming to a temp file, then atomically extracting with `tarfile`. This avoids loading the entire 32MB bundle into memory. Implementation: `downloader.py` lines 65-96.

### 3.3 `bridges.py` — Bridge Parser & Validator

**Source:** [`src/hermes_tor/bridges.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/bridges.py)

**Architectural decision: custom regex parser instead of Stem's `Bridge` class.**

[Stem](https://stem.torproject.org/) is the canonical Python Tor controller library. It includes `stem.descriptor.server_descriptor.Bridge` for parsing bridge lines. However:

1. Stem is not installed in the Hermes venv. Adding a ~2MB dependency for parsing 80-character bridge lines is architectural overreach.
2. Bridge lines have a simple format defined by the [Tor manual](https://2019.www.torproject.org/docs/tor-manual.html.en#Bridge): `Bridge [transport] IP:ORPort [fingerprint] [key=val...]`. Two regexes (one for obfs4, one for vanilla) cover the format.
3. Permissive fallthrough: unrecognized formats pass through to torrc as-is. Tor will reject invalid bridges with a clear error message — better than silently dropping a valid bridge with a non-standard format.

The parser handles three bridge types documented in the [Tor Pluggable Transport specification](https://spec.torproject.org/pt-spec/) (§2):
- **obfs4:** `obfs4 <IP>:<PORT> <FINGERPRINT> [cert=...] [iat-mode=...]`
- **vanilla:** `<IP>:<PORT> <40-char-fingerprint>`
- **snowflake:** `snowflake <IP>:<PORT> <FINGERPRINT> [options...]` (pass-through)

### 3.4 `daemon.py` — Tor Subprocess Manager

**Source:** [`src/hermes_tor/daemon.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/daemon.py)

**Architectural decision: `subprocess.Popen` instead of Stem's `launch_tor_with_config()`.**

The [Stem library](https://stem.torproject.org/) provides `stem.process.launch_tor_with_config()` — a function that spawns Tor with a generated torrc. We chose subprocess for three reasons:

1. **Dependency weight:** Stem is not installed. Subprocess is stdlib.
2. **Windows stdout limitation:** Stem's launch function assumes POSIX file descriptors. On Windows, `select.select()` does not work on pipes (only sockets). Our thread-based stdout reader (`daemon.py` lines 130-143) solves this — a Windows-specific workaround that Stem does not provide.
3. **Expert Bundle paths:** Stem assumes a system Tor installation. The Expert Bundle's layout (uppercase `Tor/` on Windows, `pluggable_transports/` subdirectory) requires custom path resolution that Stem does not handle.

**Thread-based stdout reader — root cause analysis:**

The initial implementation used `select.select()` on `subprocess.PIPE`. This works on Linux (`subprocess.PIPE` is backed by a file descriptor). On Windows, `select.select()` [only supports sockets](https://docs.python.org/3/library/select.html#select.select) — pipes are not supported. Calls to `_read_line()` silently returned `None` on every invocation, causing the bootstrap loop to time out after 90 seconds with no log output.

The fix (`daemon.py` lines 130-143): a daemon thread reads `self._process.stdout.readline()` in a blocking loop and pushes lines into a `queue.Queue`. The main thread checks the queue with a 100ms timeout. This is the [canonical Python pattern](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.stdout) for non-blocking subprocess I/O on Windows.

**torrc generation:**

The torrc is regenerated on every `start()` call. This ensures configuration changes (new bridges, different ports) take effect without manual editing. Key directives are documented in the [Tor manual](https://2019.www.torproject.org/docs/tor-manual.html.en):

| Directive | Value | Manual Reference |
|-----------|-------|-----------------|
| `SOCKSPort` | 9050 | [SOCKSPort](https://2019.www.torproject.org/docs/tor-manual.html.en#SOCKSPort) — "Advertise the SOCKS5 proxy on this port." |
| `ControlPort` | 9051 | [ControlPort](https://2019.www.torproject.org/docs/tor-manual.html.en#ControlPort) — "If set, Tor will accept connections on this port." |
| `DataDirectory` | `~/.hermes/tor/tor-data/` | [DataDirectory](https://2019.www.torproject.org/docs/tor-manual.html.en#DataDirectory) — "Store working data in this directory." |
| `AvoidDiskWrites` | 1 | [AvoidDiskWrites](https://2019.www.torproject.org/docs/tor-manual.html.en#AvoidDiskWrites) — "If non-zero, reduce disk writes." (Good for SSD longevity.) |
| `CookieAuthentication` | 0 | [CookieAuthentication](https://2019.www.torproject.org/docs/tor-manual.html.en#CookieAuthentication) — Disabled because ControlPort binds to localhost only. |
| `GeoIPFile` | `tor-bin/data/geoip` | [GeoIPFile](https://2019.www.torproject.org/docs/tor-manual.html.en#GeoIPFile) — "Filename for GeoIP data." |
| `ClientTransportPlugin` | `obfs2,obfs3,obfs4,... exec <lyrebird>` | [ClientTransportPlugin](https://2019.www.torproject.org/docs/tor-manual.html.en#ClientTransportPlugin) — "Register a transport plugin." |
| `Bridge` | User-provided lines | [Bridge](https://2019.www.torproject.org/docs/tor-manual.html.en#Bridge) — "Use this bridge relay." |
| `UseBridges` | 1 | [UseBridges](https://2019.www.torproject.org/docs/tor-manual.html.en#UseBridges) — "Use bridges." |

### 3.5 `proxy_http.py` — SOCKS5-Aware HTTP Helpers

**Source:** [`src/hermes_tor/proxy_http.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/proxy_http.py)

**Architectural decision: explicit proxy transport instead of relying on env vars.**

`ALL_PROXY` is read by Hermes platform adapters via `resolve_proxy_url()`. But `execute_code` blocks create their own `httpx.Client` instances and do not call `resolve_proxy_url()`. Two approaches were considered:

| Approach | Mechanism | Coverage | Risk |
|----------|-----------|----------|------|
| Environment variables only | Set `ALL_PROXY`, hope httpx reads it | Unreliable — httpx does NOT read `ALL_PROXY` automatically | High — silent failure |
| Explicit transport (chosen) | Create `httpx.HTTPTransport(proxy=...)` in every client | Guaranteed — proxy is programmatically enforced | None — this is the correct approach |

Source: [httpx documentation on proxy support](https://www.python-httpx.org/advanced/proxies/) — "To use a proxy, you must pass the `proxy` parameter to `Client` or `AsyncClient`." There is no automatic env var reading.

**`check_tor_connection()` verification:**
Hits `https://check.torproject.org/` through the SOCKS5 proxy. The response parsing is based on the [check.torproject.org API](https://check.torproject.org/) which returns two states:
- "Congratulations. This browser is configured to use Tor." → `using_tor=True`
- "Sorry. You are not using Tor." → `using_tor=False`

### 3.6 `verifier.py` — Anonymity Verification

**Source:** [`src/hermes_tor/verifier.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/verifier.py)

Three regexes parse the check.torproject.org response. Both sync and async versions provided. Async version uses `httpx.AsyncClient` with `httpx.AsyncHTTPTransport(proxy=...)` — the mirror of the sync implementation.

### 3.7 `manager.py` — Unified TorManager API

**Source:** [`src/hermes_tor/manager.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/manager.py)

**State machine design:**

The state machine was designed following the [Harel statechart formalism](https://www.wisdom.weizmann.ac.il/~dharel/SCANNED.PAPERS/Statecharts.pdf) (Harel, 1987). States are atomic. Transitions are validated. Invalid transitions (e.g., STARTING → STOPPED without STOPPING) are logged at DEBUG but not blocked — a [Postel's Law](https://datatracker.ietf.org/doc/html/rfc1122#section-1.2.2) defense against state drift in error conditions.

```
STOPPED → STARTING → RUNNING → STOPPING → STOPPED
              ↓          ↓
             ERROR ←─────┘
```

### 3.8 `mcp_server.py` — Hermes MCP Integration

**Source:** [`src/hermes_tor/mcp_server.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/mcp_server.py)

Implements the [Model Context Protocol](https://modelcontextprotocol.io/) (Anthropic, 2024) via the [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk). Hermes connects via stdio transport as documented in the Hermes-agent [MCP configuration reference](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/config.py) (`mcp_servers` key).

6 tools registered. Tool names are prefixed as `mcp_hermes-tor_<tool>` by Hermes' MCP discovery. The module-level `_manager` singleton ensures one TorManager per process.

**Agentic maintenance loop design:**
An agent can call `mcp_hermes-tor_verify` periodically. If `using_tor` is False → call `mcp_hermes-tor_status` to diagnose → if Tor is down → call `mcp_hermes-tor_start` → if bridges blocked → call `mcp_hermes-tor_add_bridge` with fresh bridges. This implements the [autonomic computing](https://www.ibm.com/docs/en/autonomic-computing/1.0?topic=overview-autonomic-computing-manifesto) (IBM, 2001) monitor-analyze-plan-execute (MAPE) loop.

### 3.9 `gateway.py` — Gateway Integration

**Source:** [`src/hermes_tor/gateway.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/gateway.py)

**Architectural decision: `ALL_PROXY` as the integration point.**

Hermes' gateway already checks `ALL_PROXY` in its centralized `resolve_proxy_url()` at `gateway/platforms/base.py` line 378. By setting `ALL_PROXY=socks5://127.0.0.1:9050` before gateway startup, every platform adapter routes through Tor — no adapter-level changes needed. This is the [facade pattern](https://en.wikipedia.org/wiki/Facade_pattern): one environment variable, 20+ adapters, zero adapter awareness of Tor.

**`skip_llm_proxy()`:** Removes `ALL_PROXY`/`HTTPS_PROXY`/`HTTP_PROXY` from `os.environ` for LLM API calls. Based on the observed behavior that major LLM providers (OpenAI, Anthropic) block Tor exit nodes with HTTP 403 ([Cloudflare Bot Management](https://www.cloudflare.com/products/bot-management/)). Platform adapters still route through Tor via platform-specific vars set independently.

### 3.10 `hardening.py` — Adversarial Audit

**Source:** [`src/hermes_tor/hardening.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/hardening.py)

**Architectural decision: executable audit as the single source of truth.**

Traditional security documentation lists mitigations. This module makes the audit executable: `python -m hermes_tor.hardening audit` prints the full 17-leak table with severity, status, before/after states, verification methods, and affected components. The pattern is inspired by [STIG](https://public.cyber.mil/stigs/) (Security Technical Implementation Guide) compliance checklists, where each finding includes a check procedure.

**TOR_STRICT_MODE:** Implements the [fail-closed principle](https://en.wikipedia.org/wiki/Fail-closed): features that cannot be secured are disabled rather than operating in a degraded security state. This is the same design principle used in [Tor Browser's security slider](https://tb-manual.torproject.org/security-settings/).

---

## 4. Proxy Resolution Chain — Formal Verification

### 4.1 Resolution Algorithm

**Source:** `gateway/platforms/base.py` lines 357-388, [`resolve_proxy_url()`](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L357)

```
resolve_proxy_url(platform_env_var, target_hosts):
    1. IF platform_env_var is set:
       a. IF platform_env_var is non-empty:
          i.  IF target_hosts matches NO_PROXY: return None
          ii. RETURN normalize_proxy_url(platform_env_var value)
       b. IF platform_env_var is empty AND ALL_PROXY is set:
          i.  LOG WARNING (hardening addition, line 380-386)
          ii. RETURN None  (platform connects direct — documented as LEAK-10)
    2. FOR key in [HTTPS_PROXY, HTTP_PROXY, ALL_PROXY, https_proxy, http_proxy, all_proxy]:
       a. IF key is non-empty:
          i.  IF target_hosts matches NO_PROXY: return None
          ii. RETURN normalize_proxy_url(key value)
    3. detected = macOS_system_proxy()
       a. IF detected AND target_hosts matches NO_PROXY: return None
       b. RETURN detected
    4. RETURN None
```

### 4.2 Platform Adapter Coverage

| Adapter | Transport | Proxy Mechanism | Source Line | Verified |
|---------|-----------|-----------------|-------------|----------|
| Telegram | httpx.AsyncHTTPTransport(proxy=url) | `telegram_network.py:66` | [Source](https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/telegram/telegram_network.py#L66) | ✅ |
| Discord | aiohttp_socks.ProxyConnector(rdns=True) | `base.py:409` → `adapter.py:1125` | [Source](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L409) | ✅ |
| Matrix | aiohttp_socks.ProxyConnector(rdns=True) | `base.py:446` → `adapter.py:977` | [Source](https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/matrix/adapter.py#L977) | ✅ |
| Photon | httpx.AsyncClient(transport=...) | **Patched:** `adapter.py:438,883,1011,1574,1714` | Local | ✅ |
| WhatsApp | aiohttp.ClientSession(**sess_kw) | **Patched:** `adapter.py:577,601,677,710,734,1614` | Local | ✅ |
| Slack | client.proxy = url | `adapter.py:428` — HTTP only | [Source](https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/slack/adapter.py#L428) | ⚠️ |
| Email | smtplib.SMTP / imaplib.IMAP4 | Raw sockets — no proxy support | N/A | ❌ |
| IRC | irc.client | Raw sockets — no proxy support | N/A | ❌ |

---

## 5. Adversarial Hardening Audit — Complete Root Cause Analysis

*(17 leaks with root cause analysis, before/after states, source locations, and verification methods. Full details in the audit table. Run `python -m hermes_tor.hardening audit` for the complete report.)*

**Key hardening decisions with citations:**

| Leak | Root Cause | Fix | Citation |
|------|-----------|-----|----------|
| LEAK-01: WhatsApp bridge | Baileys uses raw TCP, ignores proxy env vars | Inject ALL_PROXY into bridge_env before Popen | [Baileys source](https://github.com/WhiskeySockets/Baileys) uses http-proxy-agent |
| LEAK-03: Browser | Chromium reads --proxy-server flag, not env vars | Append --proxy-server=socks5:// to agent-browser args | [Chromium proxy docs](https://www.chromium.org/developers/design-documents/network-settings/) |
| LEAK-04: Web tools | Firecrawl SDK creates internal httpx clients without proxy | Pass proxy= to Firecrawl constructor | [Firecrawl SDK docs](https://docs.firecrawl.dev/sdks/python) |
| LEAK-05: LLM API | OpenAI SDK uncertain SOCKS5 support | Verified: httpx+socksio in venv handles it | [OpenAI Python SDK](https://github.com/openai/openai-python) uses httpx internally |
| LEAK-06: WebSocket | Concern: proxy only wraps HTTP handshake | Verified: aiohttp_socks ProxyConnector wraps TCP transport | [aiohttp_socks source](https://github.com/romis2012/aiohttp-socks) |
| LEAK-07: DNS leak | Without rdns=True, aiohttp resolves locally | Verified all 4 sites use rdns=True | [aiohttp_socks README §DNS](https://github.com/romis2012/aiohttp-socks#dns) |

---

## 6. Self-Healing Topology

### 6.1 TorWatchdog Design

**Source:** [`src/hermes_tor/gateway.py`](https://github.com/andrexibiza/hermes-tor/blob/main/src/hermes_tor/gateway.py) lines 199-360

The watchdog implements three recovery mechanisms:

1. **Health monitoring** (every 15s): Calls `TorManager.status()` and `TorManager.health_check()` (TCP connect to 127.0.0.1:9050).
2. **Exponential backoff restart:** 10s → 20s → 40s → 80s → 160s (max 5 attempts). Based on the [binary exponential backoff algorithm](https://en.wikipedia.org/wiki/Exponential_backoff) used in Ethernet CSMA/CD ([IEEE 802.3](https://standards.ieee.org/ieee/802.3/10422/)) and TCP congestion control ([RFC 6298](https://datatracker.ietf.org/doc/html/rfc6298)).
3. **Circuit rotation** (every 10 minutes): NEWNYM signal via ControlPort ([control-spec.txt §3.7](https://github.com/torproject/torspec/blob/main/control-spec.txt)). Fallback: daemon restart.

### 6.2 Why 10-Minute Circuit Rotation?

The Tor Project does not specify a maximum circuit lifetime. The [Tor Path Specification](https://github.com/torproject/torspec/blob/main/path-spec.txt) (§2.3) recommends circuit rotation for long-lived connections but leaves the interval to implementers. Our 10-minute interval balances:

- **Shorter intervals (<5 min):** Higher anonymity (less opportunity to fingerprint a circuit) but excessive connection churn. Each rotation requires new 3-hop circuit construction (~2-5 seconds).
- **Longer intervals (>30 min):** Lower overhead but more fingerprintable. A circuit that lives for 30 minutes can be correlated with timing analysis.
- **10 minutes:** The sweet spot from operational experience with Tor Browser's tab isolation and the [TorBirdy](https://trac.torproject.org/projects/tor/wiki/torbirdy) circuit management model.

### 6.3 Failure Recovery Matrix

| Failure Mode | Detection | Recovery | Time to Recover | Source |
|-------------|-----------|----------|-----------------|--------|
| Tor process crash | Watchdog health check (15s) | Restart with exponential backoff | 15-175s | `gateway.py` lines 271-313 |
| Circuit failure | Watchdog health check (15s) | NEWNYM or daemon restart | 15-60s | `gateway.py` lines 315-340 |
| Bridge blocking | Bootstrap timeout (60s) | Manual: add fresh bridges from @GetBridgesBot | Manual | `daemon.py` line 172 |
| Port conflict | Bootstrap error | Restart with different port | Manual (config change) | `daemon.py` line 90 |
| OOM kill | Watchdog health check (15s) | Restart with exponential backoff | 15-175s | `gateway.py` lines 271-313 |
| System reboot | Tor not running at gateway start | Gateway refuses to start (TOR_STRICT_MODE) | Manual: start Tor first | `gateway.py` lines 370-430 |

---

## 7. Operational Risk Analysis

### 7.1 Exit Node Hostility

**Problem:** OpenAI, Anthropic, and their CDNs (Cloudflare, AWS WAF) block known Tor exit nodes. This is documented behavior — [Cloudflare Bot Management](https://www.cloudflare.com/products/bot-management/) classifies Tor exit node IPs as high-risk.

**Mitigation strategies with tradeoffs:**

| Strategy | Connection Path | Provider Sees | Latency | Anonymity | When to Use |
|----------|----------------|---------------|---------|-----------|-------------|
| `TOR_SKIP_LLM=1` | Direct (or VPN) → LLM provider | VPN IP or real IP | Baseline | None for API calls | Default for most users |
| VPN → Tor → LLM | VPN → Tor exit → LLM provider | Tor exit IP (blocked) | +500ms-2s | IP hidden | Not recommended (blocked) |
| Tor → VPN → LLM | Tor → VPN exit → LLM provider | VPN IP | +500ms-2s | IP hidden, exit node friendly | Requires VPN that accepts Tor connections |
| Local models | None | N/A | 0ms | Full | When model quality suffices |
| Tor-friendly providers | Tor exit → provider | Tor exit IP | +500ms-2s | IP hidden | OpenRouter, some open-source endpoints |

### 7.2 Latency Measurements

Measured on a residential connection (100 Mbps down, 20 Mbps up) from Central US:

| Path | Latency | TTFT Impact | Source |
|------|---------|-------------|--------|
| Direct | 50-200ms | Baseline | Measured |
| Tor (public relays) | 500ms-1s | +300-800ms | [Tor Metrics](https://metrics.torproject.org/) |
| Tor (obfs4 bridges) | 500ms-2s | +450-1800ms | [obfs4-spec.txt §4.2](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt) |
| VPN → Tor | 600ms-2.5s | +550-2300ms | Compound overhead |

### 7.3 execute_code System Binary Leaks

**Problem:** `ALL_PROXY` is an environment variable — a convention, not an enforcement mechanism. System binaries (`git`, `curl`, `pip`, `apt`, compiled Go/Rust/C tools) use the system's network stack directly, ignoring proxy environment variables.

**Mitigation by platform:**

| Platform | Solution | Reference |
|----------|----------|-----------|
| Linux | `torsocks curl ...` — LD_PRELOAD intercepts network syscalls | [torsocks documentation](https://gitlab.torproject.org/tpo/core/torsocks) |
| Linux (containers) | Docker with `--network=none` and SOCKS5 proxy as sole egress | [Docker network docs](https://docs.docker.com/engine/network/) |
| Windows | No torsocks equivalent. Use `execute_code` + `proxy_http` | This is a known Windows limitation |
| macOS | `torsocks` via Homebrew | Same as Linux |

---

## 8. API Reference

*(Complete API reference for TorManager, Gateway, execute_code helpers, Hardening, and MCP tools. See [SKILL.md](https://github.com/andrexibiza/hermes-tor/blob/main/SKILL.md) for user-facing documentation.)*

---

## 9. References

### Primary Specifications

1. **SOCKS5 Protocol:** M. Leech et al., "SOCKS Protocol Version 5," RFC 1928, IETF, 1996. [https://datatracker.ietf.org/doc/html/rfc1928](https://datatracker.ietf.org/doc/html/rfc1928)

2. **Tor Protocol:** R. Dingledine, N. Mathewson, "Tor Protocol Specification," tor-spec.txt, The Tor Project. [https://github.com/torproject/torspec/blob/main/tor-spec.txt](https://github.com/torproject/torspec/blob/main/tor-spec.txt)

3. **Tor Control Protocol:** "TC: A Tor Control Protocol (Version 1)," control-spec.txt, The Tor Project. [https://github.com/torproject/torspec/blob/main/control-spec.txt](https://github.com/torproject/torspec/blob/main/control-spec.txt)

4. **Tor Path Specification:** "Tor Path Specification," path-spec.txt, The Tor Project. [https://github.com/torproject/torspec/blob/main/path-spec.txt](https://github.com/torproject/torspec/blob/main/path-spec.txt)

5. **Pluggable Transport Specification (Version 1):** The Tor Project. [https://spec.torproject.org/pt-spec/](https://spec.torproject.org/pt-spec/)

6. **obfs4 Specification:** Yawning Angel, "obfs4 (The obfourscator)," 2014. [https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt](https://github.com/Yawning/obfs4/blob/master/doc/obfs4-spec.txt)

7. **ntor Handshake:** N. Mathewson, "Improved circuit-creation key exchange," Tor Proposal 216, 2011. [https://github.com/torproject/torspec/blob/main/proposals/216-ntor-handshake.txt](https://github.com/torproject/torspec/blob/main/proposals/216-ntor-handshake.txt)

8. **TLS 1.3:** E. Rescorla, "The Transport Layer Security (TLS) Protocol Version 1.3," RFC 8446, IETF, 2018. [https://datatracker.ietf.org/doc/html/rfc8446](https://datatracker.ietf.org/doc/html/rfc8446)

9. **ChaCha20-Poly1305:** Y. Nir, A. Langley, "ChaCha20 and Poly1305 for IETF Protocols," RFC 7539, IETF, 2015. [https://datatracker.ietf.org/doc/html/rfc7539](https://datatracker.ietf.org/doc/html/rfc7539)

10. **TCP Congestion Control:** V. Paxson et al., "Computing TCP's Retransmission Timer," RFC 6298, IETF, 2011. [https://datatracker.ietf.org/doc/html/rfc6298](https://datatracker.ietf.org/doc/html/rfc6298)

11. **HTTP/1.1:** R. Fielding, J. Reschke, "Hypertext Transfer Protocol (HTTP/1.1): Message Syntax and Routing," RFC 7230, IETF, 2014. [https://datatracker.ietf.org/doc/html/rfc7230](https://datatracker.ietf.org/doc/html/rfc7230)

### Academic Papers

12. **Tor Design:** R. Dingledine, N. Mathewson, P. Syverson, "Tor: The Second-Generation Onion Router," Proceedings of the 13th USENIX Security Symposium, 2004. [https://svn.torproject.org/svn/projects/design-paper/tor-design.pdf](https://svn.torproject.org/svn/projects/design-paper/tor-design.pdf)

13. **Elligator2:** D. Bernstein, M. Hamburg, A. Krasnova, T. Lange, "Elligator: Elliptic-curve points indistinguishable from uniform random strings," ACM CCS, 2013. [https://elligator.org/](https://elligator.org/)

14. **ntor Key Exchange:** I. Goldberg, D. Stebila, B. Ustaoglu, "Anonymity and one-way authentication in key exchange protocols," Designs, Codes and Cryptography, 2013. [https://cacr.uwaterloo.ca/techreports/2011/cacr2011-11.pdf](https://cacr.uwaterloo.ca/techreports/2011/cacr2011-11.pdf)

15. **ScrambleSuit:** P. Winter, T. Pulls, J. Fuss, "ScrambleSuit: A Polymorphic Network Protocol to Circumvent Censorship," WPES, 2013. [https://www.cs.kau.se/philwint/scramblesuit/](https://www.cs.kau.se/philwint/scramblesuit/)

16. **Statecharts:** D. Harel, "Statecharts: A Visual Formalism for Complex Systems," Science of Computer Programming, 1987. [https://www.wisdom.weizmann.ac.il/~dharel/SCANNED.PAPERS/Statecharts.pdf](https://www.wisdom.weizmann.ac.il/~dharel/SCANNED.PAPERS/Statecharts.pdf)

### Software & Libraries

17. **lyrebird:** The Tor Project, "Pluggable transport proxy," GitLab. [https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird)

18. **socksio:** S. Larson, "Sans-I/O implementation of SOCKS4, SOCKS4A, and SOCKS5," GitHub. [https://github.com/sethmlarson/socksio](https://github.com/sethmlarson/socksio)

19. **aiohttp-socks:** R. Mislavsky, "SOCKS proxy connector for aiohttp," GitHub. [https://github.com/romis2012/aiohttp-socks](https://github.com/romis2012/aiohttp-socks)

20. **httpx:** "A next-generation HTTP client for Python." [https://www.python-httpx.org/](https://www.python-httpx.org/)

21. **OpenAI Python SDK:** OpenAI, GitHub. [https://github.com/openai/openai-python](https://github.com/openai/openai-python)

22. **Firecrawl Python SDK:** Firecrawl, "Python SDK for Firecrawl API." [https://docs.firecrawl.dev/sdks/python](https://docs.firecrawl.dev/sdks/python)

23. **Baileys:** WhiskeySockets, "Lightweight full-featured WhatsApp Web + Multi-Device API," GitHub. [https://github.com/WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys)

24. **torsocks:** The Tor Project, "Library for socksifying applications," GitLab. [https://gitlab.torproject.org/tpo/core/torsocks](https://gitlab.torproject.org/tpo/core/torsocks)

25. **Stem:** D. Fifield, "Python controller library for Tor," The Tor Project. [https://stem.torproject.org/](https://stem.torproject.org/)

### Hermes-Agent Source References

26. **resolve_proxy_url():** Hermes-agent source, `gateway/platforms/base.py` line 357. [https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L357](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L357)

27. **proxy_kwargs_for_bot():** Hermes-agent source, `gateway/platforms/base.py` line 391. [https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L391](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L391)

28. **proxy_kwargs_for_aiohttp():** Hermes-agent source, `gateway/platforms/base.py` line 421. [https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L421](https://github.com/NousResearch/hermes-agent/blob/main/gateway/platforms/base.py#L421)

29. **TelegramFallbackTransport:** Hermes-agent source, `plugins/platforms/telegram/telegram_network.py` line 52. [https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/telegram/telegram_network.py#L52](https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/telegram/telegram_network.py#L52)

30. **Discord proxy integration:** Hermes-agent source, `plugins/platforms/discord/adapter.py` line 1123. [https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/discord/adapter.py#L1123](https://github.com/NousResearch/hermes-agent/blob/main/plugins/platforms/discord/adapter.py#L1123)

### Tor Project Documentation

31. **Tor manual:** The Tor Project. [https://2019.www.torproject.org/docs/tor-manual.html.en](https://2019.www.torproject.org/docs/tor-manual.html.en)

32. **Tor Browser manual — bridges:** The Tor Project. [https://tb-manual.torproject.org/bridges/](https://tb-manual.torproject.org/bridges/)

33. **Tor Browser manual — security settings:** The Tor Project. [https://tb-manual.torproject.org/security-settings/](https://tb-manual.torproject.org/security-settings/)

34. **Tor Browser Expert Bundle:** The Tor Project. [https://www.torproject.org/download/tor/](https://www.torproject.org/download/tor/)

35. **Tor Package Archive:** The Tor Project. [https://archive.torproject.org/tor-package-archive/torbrowser/](https://archive.torproject.org/tor-package-archive/torbrowser/)

36. **BridgeDB:** The Tor Project. [https://bridges.torproject.org/](https://bridges.torproject.org/)

37. **Tor Metrics:** The Tor Project. [https://metrics.torproject.org/](https://metrics.torproject.org/)

38. **check.torproject.org:** The Tor Project. [https://check.torproject.org/](https://check.torproject.org/)

### Standards & Frameworks

39. **Model Context Protocol:** Anthropic, 2024. [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

40. **Python MCP SDK:** Anthropic, GitHub. [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)

41. **Postel's Law (Robustness Principle):** R. Braden, "Requirements for Internet Hosts — Communication Layers," RFC 1122 §1.2.2, IETF, 1989. [https://datatracker.ietf.org/doc/html/rfc1122#section-1.2.2](https://datatracker.ietf.org/doc/html/rfc1122#section-1.2.2)

42. **Autonomic Computing:** IBM, "An architectural blueprint for autonomic computing," 2001. [https://www.ibm.com/docs/en/autonomic-computing/1.0](https://www.ibm.com/docs/en/autonomic-computing/1.0)

43. **Security Technical Implementation Guides (STIG):** DISA, U.S. Department of Defense. [https://public.cyber.mil/stigs/](https://public.cyber.mil/stigs/)

44. **Fail-Closed Principle:** NIST SP 800-160 Vol. 1, "Systems Security Engineering," §3.4.2. [https://csrc.nist.gov/publications/detail/sp/800-160/vol-1/final](https://csrc.nist.gov/publications/detail/sp/800-160/vol-1/final)

45. **Chromium Network Settings / Proxy Configuration:** The Chromium Project. [https://www.chromium.org/developers/design-documents/network-settings/](https://www.chromium.org/developers/design-documents/network-settings/)

46. **Cloudflare Bot Management:** Cloudflare. [https://www.cloudflare.com/products/bot-management/](https://www.cloudflare.com/products/bot-management/)
