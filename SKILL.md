# Hermes Tor — Complete Guide

Route ALL Hermes agent communication through Tor bridges for anonymity. Covers gateway platforms, subagents, `execute_code` blocks, MCP tools, bridge management, VPN layering, and troubleshooting.

## Architecture

**The threat model:** Governments and ISPs are moving to regulate who you get your AI from. They can block API endpoints, throttle connections, or monitor which models you use. Tor bridges make Hermes uncensorable — your AI traffic is cryptographically protected end-to-end, indistinguishable from random noise. No ISP, government, or intermediary can see which AI provider you're talking to, or stop you from talking to them. Your tokens, your models, your freedom.

Hermes already has a centralized proxy resolver at `gateway/platforms/base.py`. Every platform adapter calls `resolve_proxy_url()`, which checks:

1. Platform-specific env var (`TELEGRAM_PROXY`, `DISCORD_PROXY`, `PHOTON_PROXY`, `WHATSAPP_PROXY`, `MATRIX_PROXY`)
2. `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` (case-insensitive)
3. macOS system proxy (auto-detect)

**The magic:** Set `ALL_PROXY=socks5://127.0.0.1:9050` before the gateway starts, and ALL platform adapters automatically route through Tor.

```
┌──────────────────────────────────────────────────────┐
│  Tor Expert Bundle (tor.exe + lyrebird)              │
│  SOCKS5 proxy: 127.0.0.1:9050                       │
│  obfs4 bridges from @GetBridgesBot                   │
└──────────────────┬───────────────────────────────────┘
                   │ ALL_PROXY=socks5://127.0.0.1:9050
┌──────────────────▼───────────────────────────────────┐
│  Hermes Gateway                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ Telegram │ │ Discord  │ │ Matrix   │  ... 20+    │
│  │ SOCKS5 ✅│ │ SOCKS5 ✅│ │ SOCKS5 ✅│  platforms  │
│  └──────────┘ └──────────┘ └──────────┘             │
└──────────────────────────────────────────────────────┘
```

## Setup

### 1. Install hermes-tor

```bash
git clone https://github.com/andrexibiza/hermes-tor.git
cd hermes-tor
uv sync --extra mcp
uv pip install -e .
```

### 2. Get Bridges

Message **@GetBridgesBot** on Telegram and send `/bridges`. You'll receive obfs4 bridge lines like:

```
obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0
obfs4 5.6.7.8:80 FINGERPRINT cert=... iat-mode=1
```

Save them to `~/.hermes/tor/bridges.txt` (one per line), or use the `tor_add_bridge` MCP tool.

**Why bridges?** Public Tor relays are listed and easily blocked by ISPs and censors. Bridges are unlisted entry points — your ISP can't distinguish bridge traffic from random encrypted data. This is essential for "uncensorable and unstoppable" operation.

### 3. Download Tor

```bash
python -c "from hermes_tor.downloader import download_tor_binary; download_tor_binary()"
```

Downloads ~22MB (Windows) or ~32MB (Linux). One-time.

### 4. Start Tor + Gateway

```bash
# Start Tor, inject ALL_PROXY, then launch gateway
python -m hermes_tor.gateway --timeout 90 -- hermes gateway run

# Or start Tor first, then gateway separately:
python -c "
from hermes_tor.gateway import start_tor_for_gateway
mgr = start_tor_for_gateway()
# Tor is running, ALL_PROXY is set, gateway will auto-route
"
hermes gateway run
```

### 5. Verify

```bash
python -c "
import os
os.environ['TOR_ENABLED'] = '1'
from hermes_tor.proxy_http import check_tor_connection
print(check_tor_connection())
"
# Expected: {'tor_available': True, 'using_tor': True, 'exit_ip': '185.220.x.x'}
```

## Platform Coverage

| Platform | Tor Support | Env Var | Notes |
|----------|------------|---------|-------|
| Telegram | ✅ SOCKS5 | `TELEGRAM_PROXY` | Built-in. `TelegramFallbackTransport` passes proxy to httpx. |
| Discord | ✅ SOCKS5 | `DISCORD_PROXY` | Built-in. `aiohttp_socks.ProxyConnector` with `rdns=True`. |
| Matrix | ✅ SOCKS5 | `MATRIX_PROXY` | Built-in. |
| Photon (iMessage) | ✅ SOCKS5 | `PHOTON_PROXY` | Patched. 5 httpx client sites now call `resolve_proxy_url()`. |
| WhatsApp | ✅ SOCKS5 | `WHATSAPP_PROXY` | Patched. 6 aiohttp session sites now use `proxy_kwargs_for_aiohttp()`. |
| Slack | ⚠️ HTTP only | (auto) | Slack SDK's `client.proxy` rejects SOCKS. Use Tor HTTP proxy or privoxy. |
| IRC | ❌ | — | Raw TCP sockets. Protocol limitation. |
| Email | ❌ | — | Raw SMTP/IMAP sockets. |
| SMS | ✅ | (auto) | Twilio API — uses httpx, routes through ALL_PROXY. |
| Web tools | ⚠️ Partial | — | `web_search`/`web_extract` SDKs may not route. Use `proxy_http` in execute_code. |
| LLM API calls | ✅ | (auto) | OpenAI SDK respects proxy env vars. API key identifies account. |
| Browser tool | ❌ | — | Local agent-browser doesn't expose SOCKS5. Browserbase paid tier does. |

## MCP Tools

Register the MCP server:

```bash
hermes mcp add hermes-tor --command "uv" --args "run" --args "--directory" --args "/path/to/hermes-tor" --args "python" --args "-m" --args "hermes_tor.mcp_server"
```

| Tool | Description |
|------|------------|
| `tor_download` | Download Tor Expert Bundle (~22-32MB). One-time. |
| `tor_start` | Start Tor daemon with bridges from `~/.hermes/tor/bridges.txt`. |
| `tor_stop` | Stop Tor daemon gracefully. |
| `tor_status` | Get state, SOCKS5 URL, bridge count, circuit status, uptime. |
| `tor_verify` | Hit `check.torproject.org` through the SOCKS5 proxy. Reports exit IP. |
| `tor_add_bridge` | Add a bridge line. Persisted to `~/.hermes/tor/bridges.txt`. |

## Usage Patterns

### Gateway with Tor (All Platforms)

```bash
python -m hermes_tor.gateway -- hermes gateway run
```

### execute_code with Tor

```python
import os
os.environ["TOR_ENABLED"] = "1"

from hermes_tor.proxy_http import tor_get, tor_post, check_tor_connection

# Verify
status = check_tor_connection()
print(f"Using Tor: {status['using_tor']}, Exit IP: {status['exit_ip']}")

# Anonymous HTTP
data = tor_get("https://httpbin.org/ip")
data = tor_post("https://api.example.com/data", json={"key": "value"})
```

### Subagents with Tor

Subagents run in ThreadPoolExecutor threads — they inherit `os.environ` automatically.

```python
from hermes_tor.gateway import inject_gateway_env

# Before spawning subagents:
inject_gateway_env()  # ALL_PROXY + HTTPS_PROXY + HTTP_PROXY + TOR_ENABLED

# Now delegate — subagent sees all proxy env vars
# delegate_task(goal="research anonymously", ...)
```

### Terminal Commands with Tor (Linux)

```bash
torsocks curl https://check.torproject.org/
torsocks python script.py
```

Not available on Windows. Use `execute_code` + `proxy_http` instead.

## VPN + Tor Layering

**Recommended: VPN → Tor → destination**

```
You → VPN (encrypts all traffic from your machine)
        → Tor (routes through 3-hop circuit + bridges)
            → Destination
```

**Why layer VPN + Tor:**
- VPN hides Tor usage from your ISP (they see VPN traffic, not Tor traffic)
- Tor provides anonymity at the application layer
- VPN provides an additional jurisdiction hop
- If Tor fails, your real IP is still hidden behind the VPN

**Setup order:**
1. Connect to VPN first (Mullvad, ProtonVPN, IVPN recommended)
2. Start Tor with bridges
3. Start Hermes gateway

**Critical:** Connect VPN BEFORE Tor. Tor's guard relay selection is sticky — if you connect Tor without VPN, your guard relay is associated with your real IP. Restart Tor after connecting VPN to get a fresh guard.

**What this protects:**
- ISP can't see you're using Tor (VPN encryption)
- ISP can't block Tor (VPN bypasses ISP-level blocking)
- Tor exit node can't see your real IP (VPN is between you and Tor entry)
- If VPN drops, Tor circuit breaks — no leak

**What this doesn't protect:**
- VPN provider knows you're connecting to Tor relays
- Your VPN account is tied to a payment method
- Tor exit nodes can see unencrypted traffic (same as always — use HTTPS)

**Recommended VPN providers for this pattern:**
- Mullvad (accepts cash/crypto, no email required)
- ProtonVPN (Swiss jurisdiction, strong privacy laws)
- IVPN (accepts cash/crypto, no logs)

## Bridge Management

### Getting Bridges

1. **Telegram:** @GetBridgesBot — send `/bridges` (fastest, most reliable)
2. **Web:** https://bridges.torproject.org/bridges?transport=obfs4
3. **Email:** bridges@torproject.org (from Gmail/Riseup, body: `get transport obfs4`)

### Rotating Bridges

Bridges get blocked over time. Rotate daily:

```bash
# Manual rotation
tor_add_bridge "obfs4 NEW_IP:PORT FINGERPRINT cert=... iat-mode=0"
tor_stop
tor_start
tor_verify

# Automated rotation (daily cron job)
hermes cron create "0 0 * * *" \
  --name "Tor Bridge Rotation" \
  --script tor_rotate_bridges.py \
  --no-agent
```

### Bridge Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `tor_start` times out | All bridges blocked | Get fresh bridges from @GetBridgesBot |
| Tor connects but slow | Some bridges slow/dead | Try different bridges; obfs4 preferred |
| "lyrebird not found" | Tor bundle corrupted | Re-run `tor_download` |
| Bridge line rejected | Wrong format | Copy exactly from @GetBridgesBot output |

## Persistent Configuration

To survive gateway restarts, write config to `~/.hermes/.env`:

```bash
python -c "
from hermes_tor.gateway import start_tor_for_gateway
mgr = start_tor_for_gateway(write_env=True)
print('Tor running, ALL_PROXY saved to ~/.hermes/.env')
"
```

The gateway loads `~/.hermes/.env` at startup (line 1422 of `gateway/run.py`), so Tor routing persists across restarts.

To remove Tor routing from `.env`:

```bash
python -c "
from hermes_tor.gateway import remove_gateway_env_file
remove_gateway_env_file()
"
```

## Operational Risks & Tradeoffs

### LLM Exit Node Hostility

OpenAI, Anthropic, and their API gateways (Cloudflare, AWS WAF) aggressively block traffic from known Tor exit nodes. You will see HTTP 403, 429, or invisible CAPTCHA challenges. This is not a bug — it's the providers protecting their APIs.

**Solution:** `TOR_SKIP_LLM=1` routes LLM API calls direct (or through VPN) while keeping all other traffic through Tor. The API key already identifies your account — Tor adds IP privacy but not account anonymity for API calls. For truly anonymous LLM access, use local models or providers that don't block Tor.

```python
from hermes_tor.gateway import skip_llm_proxy
skip_llm_proxy()  # Removes ALL_PROXY/HTTPS_PROXY/HTTP_PROXY for LLM calls
```

### Tor Latency

3-hop Tor circuit + obfs4 bridges adds 500ms-2s latency. Streaming TTFT (Time To First Token) will spike. Batch API calls are less affected — the hit is on connection setup, not per-token.

**Tradeoff:** For streaming chat, use `TOR_SKIP_LLM=1`. For batch workloads (subagent research, scheduled tasks), Tor overhead is negligible.

### execute_code System Binary Leaks

`ALL_PROXY` is a polite request, not a physical barrier. System binaries (`git`, `curl`, `pip`, compiled tools) ignore proxy env vars. On Linux, wrap with `torsocks`. On Windows, use `execute_code` + `proxy_http` instead of shelling out.

## Troubleshooting

### Tor won't bootstrap

```bash
# Check bridges file
cat ~/.hermes/tor/bridges.txt

# Try with public relays first (remove bridges temporarily)
mv ~/.hermes/tor/bridges.txt ~/.hermes/tor/bridges.txt.bak
tor_start  # should connect via public relays
tor_verify # confirm it works
# If public relays work but bridges don't, your bridges are blocked

# Restore bridges
mv ~/.hermes/tor/bridges.txt.bak ~/.hermes/tor/bridges.txt
# Get fresh bridges from @GetBridgesBot
```

### check.torproject.org says "not using Tor"

1. Verify Tor is running: `tor_status`
2. Verify `ALL_PROXY` is set: `echo $ALL_PROXY`
3. Test with `proxy_http`:
```python
import os; os.environ['TOR_ENABLED'] = '1'
from hermes_tor.proxy_http import check_tor_connection
print(check_tor_connection())
```

### Platform-specific issues

**Telegram not connecting through Tor:**
```bash
export TELEGRAM_PROXY=socks5://127.0.0.1:9050
```

**Discord voice not working:**
SOCKS5 proxying adds latency. Voice may be choppy. Discord voice uses UDP — SOCKS5 only proxies TCP. This is a protocol limitation.

**WhatsApp bridge can't connect:**
The WhatsApp bridge connects to `127.0.0.1` (localhost). Localhost connections bypass the proxy (NO_PROXY behavior). This is correct — the bridge is local, only the bridge-to-WhatsApp-server connection needs Tor. The bridge handles its own connection internally.

### Windows-specific

- No `torsocks` available. Use `execute_code` + `proxy_http` for terminal-level anonymity.
- Tor Expert Bundle uses `Tor/tor.exe` (capital T). Paths are resolved correctly by `constants.py`.
- Process management uses `terminate()` instead of `SIGINT`.

### Tor + VPN: Kill Switch

To prevent leaks if Tor dies:

```bash
# Linux: iptables rule to block all non-Tor traffic
iptables -A OUTPUT -p tcp --dport 9050 -j ACCEPT   # Allow Tor SOCKS
iptables -A OUTPUT -m owner --uid-owner tor -j ACCEPT # Allow Tor daemon
iptables -A OUTPUT -j DROP                            # Block everything else

# Or use a VPN with built-in kill switch (Mullvad, ProtonVPN)
```

## Anti-Patterns

- **Don't skip bridges.** Public relays are easily blocked. Bridges are essential for uncensorable operation.
- **Don't run Tor without a VPN** if your threat model includes ISP-level surveillance.
- **Don't share bridges publicly.** Bridges in `bridges.txt` are private. Never commit them to git.
- **Don't route LLM API calls expecting account anonymity.** The API key in request headers identifies your account regardless of IP.
- **Don't expect voice/video to work well through Tor.** UDP doesn't proxy through SOCKS5. Use text-only for anonymous communication.

## Adversarial Hardening Audit

14 leaks identified and locked down in an adversarial code review. Every outbound connection path traced.

| Leak | Status | Description |
|------|--------|-------------|
| LEAK-01 | ✅ FIXED | WhatsApp bridge subprocess — Node.js bridge now receives ALL_PROXY/HTTPS_PROXY/HTTP_PROXY |
| LEAK-02 | ⚠️ MITIGATED | Photon sidecar binary — ALL_PROXY/GRPC_PROXY injected; gRPC proxy depends on Go binary |
| LEAK-03 | ✅ FIXED | Browser tool — `--proxy-server=socks5://127.0.0.1:9050` passed to Chromium |
| LEAK-04 | ✅ FIXED | Web tools SDK — Firecrawl client receives proxy parameter |
| LEAK-05 | ✅ FIXED | LLM API calls — verified OpenAI SDK routes through SOCKS5 via httpx+socksio |
| LEAK-06 | ✅ FIXED | WebSocket proxy persistence — verified aiohttp_socks ProxyConnector handles full lifecycle |
| LEAK-07 | ✅ FIXED | DNS leak — verified rdns=True on all aiohttp connectors |
| LEAK-08 | ✅ FIXED | Slack SOCKS5 blocked — elevated to WARNING with privoxy workaround |
| LEAK-09 | ✅ FIXED | Gateway restart race — TOR_HEALTH flag prevents startup on dead proxy |
| LEAK-10 | ✅ FIXED | Platform env override — warns when empty platform var overrides ALL_PROXY |
| LEAK-11 | 📄 DOCUMENTED | Discord voice UDP — SOCKS5 protocol limitation |
| LEAK-12 | 📄 DOCUMENTED | Email SMTP/IMAP — Python smtplib/imaplib don't support SOCKS5 |
| LEAK-13 | 📄 DOCUMENTED | IRC — raw TCP sockets |
| LEAK-14 | 📄 DOCUMENTED | Import-time network calls — audited; no leaks found in major adapters |
| LEAK-15 | 📄 DOCUMENTED | LLM exit node hostility — providers block Tor IPs (403/429); use TOR_SKIP_LLM=1 |
| LEAK-16 | 📄 DOCUMENTED | execute_code system binary leaks — git/curl/pip bypass proxy; use torsocks on Linux |
| LEAK-17 | 📄 DOCUMENTED | Tor latency (500ms-2s TTFT) — use TOR_SKIP_LLM=1 for streaming, Tor for batch |

**TOR_STRICT_MODE**: Set `TOR_STRICT_MODE=1` to block all documented-leaky features (Discord voice, Email, IRC). Gateway refuses to start if Tor health check fails.
Full audit: `python -m hermes_tor.hardening audit`

## Reference

- Tor Project: https://torproject.org
- BridgeDB: https://bridges.torproject.org
- Tor Metrics (exit node list): https://metrics.torproject.org
- check.torproject.org: https://check.torproject.org
- hermes-tor repo: https://github.com/andrexibiza/hermes-tor
