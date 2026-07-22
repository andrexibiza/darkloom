# Hermes-Tor Proxy Architecture

## How Hermes Gateway Routes Through Tor

Hermes already has a complete SOCKS5 proxy system built into its gateway. The missing piece was setting `ALL_PROXY=socks5://127.0.0.1:9050` and patching two platform adapters that bypass the centralized resolver.

### The Proxy Resolution Chain

Every platform adapter calls `resolve_proxy_url()` from `gateway/platforms/base.py`:

```
resolve_proxy_url(platform_env_var=None, target_hosts=None)
```

Resolution priority:
1. Platform-specific env var (e.g., `TELEGRAM_PROXY`, `DISCORD_PROXY`)
2. `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` (case-insensitive)
3. macOS system proxy (auto-detect via `scutil --proxy`)

When `ALL_PROXY=socks5://127.0.0.1:9050` is set in the environment before the gateway starts, **every platform adapter that calls `resolve_proxy_url()` automatically routes through Tor**.

### Per-Platform Proxy Status

| Platform | Proxy Support | Env Var | Mechanism | Patch Needed |
|----------|--------------|---------|-----------|--------------|
| **Telegram** | ✅ SOCKS5 | `TELEGRAM_PROXY` | `httpx.AsyncHTTPTransport(proxy=...)` | None |
| **Discord** | ✅ SOCKS5 | `DISCORD_PROXY` | `aiohttp_socks.ProxyConnector(rdns=True)` | None |
| **Matrix** | ✅ SOCKS5 | `MATRIX_PROXY` | `resolve_proxy_url()` | None |
| **Slack** | ⚠️ HTTP only | (auto) | Slack SDK `client.proxy = url` — SOCKS blocked | None (limitation) |
| **Photon (iMessage)** | ✅ SOCKS5 | `PHOTON_PROXY` | `httpx.AsyncHTTPTransport(proxy=...)` | `0001-photon-proxy.patch` |
| **WhatsApp** | ✅ SOCKS5 | `WHATSAPP_PROXY` | `aiohttp.ClientSession(connector=ProxyConnector)` | `0002-whatsapp-proxy.patch` |
| **IRC** | ❌ N/A | — | Raw TCP sockets | None (protocol limitation) |
| **Email (SMTP/IMAP)** | ❌ N/A | — | Raw sockets | None (protocol limitation) |
| **SMS** | ❌ N/A | — | Twilio API via HTTP (already goes through httpx) | None |
| **Web tools** | ❌ | — | Raw httpx clients — no proxy support | Separate PR needed |
| **LLM API calls** | ❌ | — | Provider router creates own httpx clients | Separate PR needed |

### Integration Flow

```
┌─────────────────────────────────────────────────────────┐
│  1. Start Tor daemon                                     │
│     hermes-tor starts tor.exe with bridges               │
│     SOCKS5 proxy on 127.0.0.1:9050                       │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  2. Inject ALL_PROXY                                     │
│     ALL_PROXY=socks5://127.0.0.1:9050                    │
│     HTTPS_PROXY=socks5://127.0.0.1:9050                  │
│     HTTP_PROXY=socks5://127.0.0.1:9050                   │
│     Written to ~/.hermes/.env for persistence            │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  3. Start Hermes Gateway                                 │
│     Gateway loads ~/.hermes/.env at startup              │
│     Each platform adapter calls resolve_proxy_url()      │
│     → ALL_PROXY found → routes through Tor SOCKS5        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  4. All platform traffic routes through Tor              │
│     • Telegram API calls → Tor exit node                 │
│     • Discord WebSocket → Tor exit node                  │
│     • Matrix federation → Tor exit node                  │
│     • Photon iMessage sidecar → Tor exit node            │
│     • WhatsApp bridge → Tor exit node                    │
│     • Slack API calls → Tor exit node (HTTP only)        │
└─────────────────────────────────────────────────────────┘
```

## What Is and Isn't Covered

### ✅ Covered (routes through Tor)

- **Telegram**: All API calls (getUpdates, sendMessage, etc.) via httpx SOCKS5 transport
- **Discord**: WebSocket gateway + REST API via aiohttp_socks ProxyConnector
- **Matrix**: Federation and client-server API via mautrix with SOCKS5 connector
- **Photon**: After applying `0001-photon-proxy.patch` — all sidecar HTTP calls
- **WhatsApp**: After applying `0002-whatsapp-proxy.patch` — bridge health checks + API calls
- **Slack**: HTTP proxy only (Slack SDK rejects SOCKS — Tor exit node IP is still hidden via HTTP proxy)
- **Subagent `execute_code` blocks**: Via `proxy_http` module (TOR_ENABLED=1)
- **`terminal` commands (Linux)**: Via `torsocks` preload

### ⚠️ Partial Coverage

- **Slack**: Routes through Tor HTTP proxy but can't use SOCKS5. Slack SDK's `client.proxy` only accepts `http://` URLs. A Tor HTTP proxy (like Privoxy) would be needed for full coverage. This is documented as a Slack SDK limitation.
- **LLM API calls**: The TCP connection can go through Tor if `ALL_PROXY` affects the provider router's httpx clients, BUT the API key in request headers identifies the account. Tor provides IP-level anonymity but not account-level anonymity for API calls.

### ❌ Not Covered

- **Email (SMTP/IMAP)**: Raw socket connections don't use HTTP. Would need a SOCKS5-aware email client or a transparent proxy.
- **IRC**: Raw TCP sockets — same limitation as email.
- **Web tools (`web_search`, `web_extract`)**: Hermes creates raw httpx clients without proxy configuration. Separate PR needed.
- **Browser tool**: agent-browser doesn't expose SOCKS5 proxy config. Browserbase paid tier supports custom proxy.
- **`terminal` commands (Windows)**: No torsocks equivalent. Use `execute_code` blocks instead.

## Usage

### Quick Start: Gateway with Tor

```bash
# One-time: download Tor binary
python -m hermes_tor.mcp_server  # then use tor_download tool

# Add bridges (from @GetBridgesBot on Telegram)
# Save to ~/.hermes/tor/bridges.txt

# Start gateway with Tor routing
python -m hermes_tor.gateway -- hermes gateway run

# Or with longer bootstrap timeout
python -m hermes_tor.gateway --timeout 90 -- hermes gateway run
```

### Persistent Config (survives gateway restarts)

```bash
# Start Tor once, write config to ~/.hermes/.env
python -c "
from hermes_tor.gateway import start_tor_for_gateway
mgr = start_tor_for_gateway()
print('Tor running — gateway will auto-route through Tor on next start')
"

# Then start gateway normally — it reads ALL_PROXY from .env
hermes gateway run
```

### Verify Everything Routes Through Tor

```bash
# While gateway is running, in another terminal:
python -c "
import os
os.environ['TOR_ENABLED'] = '1'
from hermes_tor.proxy_http import check_tor_connection
print(check_tor_connection())
"
```

## Applying Core Patches

The patches in `patches/` directory are for Hermes-agent core. They add proxy support to platform adapters that currently bypass the centralized resolver.

```bash
# In the hermes-agent repo:
cd ~/.hermes/hermes-agent

# Apply Photon proxy patch
git apply ~/1_Projects/hermes-tor/patches/0001-photon-proxy.patch

# Apply WhatsApp proxy patch
git apply ~/1_Projects/hermes-tor/patches/0002-whatsapp-proxy.patch

# Restart gateway
hermes gateway restart
```

## Architecture Decisions

### Why ALL_PROXY and not per-platform vars?

Setting `ALL_PROXY=socks5://127.0.0.1:9050` covers every platform adapter in one variable because `resolve_proxy_url()` falls back to it. Per-platform vars (`TELEGRAM_PROXY`, `DISCORD_PROXY`) are still available for granular control — e.g., route Discord through a different proxy or disable Tor for one platform by setting `DISCORD_PROXY=`.

### Why write to .env instead of just os.environ?

The Hermes gateway is a long-lived process. If it crashes and the supervisor restarts it, the new process won't have the runtime `os.environ` injection. Writing to `~/.hermes/.env` ensures Tor routing persists across gateway restarts and system reboots.

### Why Tor bridges instead of public relays?

Bridges are not publicly listed — ISPs and censors can't easily block them. Public relays are known and frequently blocked in restricted networks. For "uncensorable and unstoppable" operation, bridges are essential.

### Why SOCKS5 and not HTTP proxy?

Tor natively speaks SOCKS5. Adding an HTTP proxy layer (like Privoxy) adds latency, complexity, and another process to manage. `httpx` supports SOCKS5 natively via `socksio`. `aiohttp` supports SOCKS5 via `aiohttp-socks`. Both are already in the Hermes dependency tree.
