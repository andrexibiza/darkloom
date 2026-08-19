# Darkloom Proxy Architecture

## Architecture statement

Darkloom is not a universal transparent proxy. It is a bounded transport harness around explicitly owned operations, plus a semantic compatibility contract with Hermes Agent.

```text
Darkloom-owned operation
    -> typed policy decision
    -> explicit proxy-aware transport
    -> Tor SOCKS listener
    -> runtime routing probe
    -> evidence record

Hermes-owned operation outside boundary
    -> preserve native behavior
    -> report unsupported/unverified state
    -> make no Darkloom routing claim
```

## Process environment

Darkloom owns the generic process-level variables it injects:

```text
ALL_PROXY / all_proxy
HTTPS_PROXY / https_proxy
HTTP_PROXY / http_proxy
TOR_PROXY / tor_proxy
NO_PROXY / no_proxy
TOR_ENABLED
TOR_HEALTH
```

Darkloom does not overwrite platform-specific variables such as:

```text
TELEGRAM_PROXY
DISCORD_PROXY
MATRIX_PROXY
PHOTON_PROXY
WHATSAPP_PROXY
SLACK_PROXY
GRPC_PROXY
```

Those values are upstream routing state and may represent a platform-specific bridge, direct path, or unsupported configuration.

## Strict-mode decision table

| Operation | Owner | Proxy-aware and valid | Result |
|---|---|---:|---|
| Darkloom HTTP/MCP/browser/web/LLM | Darkloom | yes | allow |
| Darkloom HTTP/MCP/browser/web/LLM | Darkloom | no | deny before I/O |
| Darkloom subprocess | Darkloom | known proxy-aware command | allow |
| Darkloom subprocess | Darkloom | unknown/non-proxy-aware | deny before launch |
| Discord Voice | Hermes | not SOCKS-capable | preserve; no claim |
| SMTP/IMAP/IRC | Hermes | not verified | preserve; no claim |
| Unknown future Hermes transport | Hermes | unknown | preserve as unverified |
| Unknown Darkloom-owned transport | Darkloom | unknown | deny |

## Local IPC

Loopback traffic between Hermes and a local sidecar or bridge is not automatically an external privacy leak. The external connection created by that sidecar is the surface that requires routing proof.

Do not proxy local health checks or control sockets merely to make a coverage table look complete.

## Browser boundary

Hermes can launch multiple browser backends. A `--proxy-server` flag on one Chromium fallback proves only that exact launch path. Browser coverage must be recorded per backend, launch command, profile, and effective network probe.

## Firecrawl boundary

A local Firecrawl SDK request and the remote service's target-site fetch are separate network operations. Proxying the local API request does not prove that the remote fetch originated from the user's Tor circuit.

## Slack boundary

Slack's effective transport may require an HTTP proxy bridge rather than direct SOCKS. An unsupported SOCKS URL must not silently become a direct-routing claim. Slack remains usable, and its effective transport is reported honestly.

## DNS

Remote DNS is a per-client property. A SOCKS URL, `socks5h`, or one library's `rdns=True` setting is not proof for every subprocess, SDK, WebSocket client, or sidecar.

## Runtime proof

See `docs/TECHNICAL_REFERENCE.md` for the evidence schema and `scripts/check_upstream_alignment.py` for static compatibility checks.
