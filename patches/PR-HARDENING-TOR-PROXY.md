# PR: Hardening — Route all subprocess & SDK traffic through Tor proxy

## Summary

Hermes already had a centralized proxy resolver (`resolve_proxy_url`) that routes external platform adapter traffic through `ALL_PROXY`/`HTTPS_PROXY`. Several subprocess spawn points and SDK client constructions were **bypassing the resolver entirely** — creating direct external connections that leaked the real IP even when `ALL_PROXY=socks5://127.0.0.1:9050` was configured. Gateway requests to local bridges and sidecars remain direct so their credentials and payloads are never disclosed to the configured proxy.

This PR closes every gap found in an adversarial code audit of all outbound connection paths.

## Changes

### 1. WhatsApp bridge subprocess env injection
**File:** `plugins/platforms/whatsapp/adapter.py`  
**Before:** `bridge_env = with_hermes_node_path()` — no proxy vars passed. Node.js bridge (Baileys) connected to WhatsApp servers direct.  
**After:** `ALL_PROXY`, `HTTPS_PROXY`, `HTTP_PROXY` explicitly copied from `os.environ` into `bridge_env` before `subprocess.Popen`. Baileys reads these via `http-proxy-agent`.

### 2. Photon sidecar subprocess env injection
**File:** `plugins/platforms/photon/adapter.py`  
**Before:** `env = os.environ.copy()` — inherited parent env but no explicit proxy injection. Go sidecar uses gRPC which ignores `ALL_PROXY`.  
**After:** `ALL_PROXY`, `HTTPS_PROXY`, `HTTP_PROXY`, `GRPC_PROXY`, `https_proxy` explicitly injected. gRPC reads `GRPC_PROXY` and `HTTPS_PROXY` for proxy dialing. Residual risk: Go binary must support these vars.

### 3. Browser tool `--proxy-server` flag
**File:** `tools/browser_tool.py`  
**Before:** agent-browser launched Chromium without `--proxy-server`. Chromium ignored inherited `ALL_PROXY` env var. Every browser navigation leaked the real IP.  
**After:** When `ALL_PROXY` contains `socks5://`, `--proxy-server` is appended to agent-browser args. Chromium routes all HTTP/HTTPS/WebSocket/WebRTC through the SOCKS5 proxy. DNS also goes through proxy (Chromium default with SOCKS5).

### 4. Firecrawl SDK proxy parameter
**File:** `plugins/web/firecrawl/provider.py`  
**Before:** `Firecrawl(api_key=...)` — no proxy parameter. Firecrawl SDK uses httpx internally but doesn't read `ALL_PROXY`. All web_search/web_extract leaked real IP to backend.  
**After:** `proxy_url` resolved from `ALL_PROXY`/`HTTPS_PROXY`/`TOR_PROXY`, passed as `Firecrawl(proxy=proxy_url)`. SDK passes to its internal httpx client.

### 5. Slack SOCKS5 warning elevation
**File:** `plugins/platforms/slack/adapter.py`  
**Before:** `_resolve_slack_proxy_url()` logged SOCKS5 rejection at `INFO` level (silent). Slack connected direct without any indication to the user.  
**After:** When `ALL_PROXY=socks5://` is detected, logs at `WARNING` level with explicit message: "Slack connections will NOT route through Tor. To fix: use privoxy." Users know immediately that Slack is leaking.

### 6. Platform-env-var override warning
**File:** `gateway/platforms/base.py`  
**Before:** `DISCORD_PROXY=` (empty string) silently overrode `ALL_PROXY=socks5://...` in `resolve_proxy_url()`. Users who previously set empty platform vars to disable broken proxies had Tor silently disabled per-platform with no warning.  
**After:** When a platform-specific env var exists but is empty AND `ALL_PROXY` is set, `resolve_proxy_url()` logs at `WARNING`: "`DISCORD_PROXY` is set but empty — Discord will NOT use `ALL_PROXY=socks5://...`. Unset `DISCORD_PROXY` to route through Tor."

## Impact

Six upstream files are updated with no breaking changes. External traffic is conditionally routed through Tor when a proxy is configured, while gateway-to-local-bridge traffic continues to bypass the proxy.

## Verification

- WhatsApp bridge: `ALL_PROXY` confirmed in `bridge_env` before `Popen` 
- Photon sidecar: `GRPC_PROXY` confirmed in env dict  
- Photon gateway-to-sidecar health and API requests remain direct
- WhatsApp gateway-to-bridge health and API requests remain direct
- Browser tool: `--proxy-server=socks5://127.0.0.1:9050` confirmed in agent-browser args
- Firecrawl: `proxy=` kwarg confirmed in client constructor
- Slack: `logger.warning(...)` confirmed on SOCKS5 detection
- Base: empty-var warning confirmed in `resolve_proxy_url()`

## Related

- hermes-tor package: https://github.com/andrexibiza/hermes-tor
- Adversarial hardening audit: `python -m hermes_tor.hardening audit`
- Full architecture docs: `docs/PROXY_ARCHITECTURE.md`
