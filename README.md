# Darkloom

**A bounded privacy-transport harness and semantic compatibility layer for Hermes Agent.**

Darkloom runs and verifies the network operations it owns. It does **not** take ownership of every transport Hermes implements, and it does not break native Hermes features merely because their routing is unsupported or unverified.

## Current compatibility baseline

| Surface | Value |
|---|---|
| Hermes repository | `NousResearch/hermes-agent` |
| Reviewed commit | `2eb0b3b2c895e4a6f99714a52d35578088ad8ec7` |
| Compatibility model | Semantic source contracts + exact revision |
| Runtime routing claims | Require runtime evidence |
| Historical patches | Provenance only; never auto-applied |

The exact baseline and control ledger live in [`src/darkloom/compatibility-manifest.json`](src/darkloom/compatibility-manifest.json).

## The boundary

Darkloom owns:

- its Tor daemon lifecycle;
- bridge acquisition and custody;
- explicit proxy-aware HTTP and MCP clients;
- the environment it injects for Darkloom-launched gateway processes;
- network-policy decisions for operations Darkloom constructs;
- runtime verification artifacts produced by Darkloom.

Hermes owns:

- native platform behavior and feature availability;
- platform-specific routing configuration;
- transports Darkloom does not construct;
- future upstream capabilities outside Darkloom's declared boundary.

That produces one hard rule:

> **Darkloom fails closed inside its own mutation boundary. Outside that boundary, Hermes features remain available and Darkloom reports the coverage gap.**

## Coverage states

| Status | Meaning | Runtime behavior |
|---|---|---|
| `verified` | Darkloom-owned operation has explicit transport and runtime proof | Allowed and reportable as verified |
| `darkloom_required` | Darkloom owns the operation but proof/transport is incomplete | Denied in strict mode |
| `upstream_native` | Hermes owns the security/routing behavior | Verified semantically; no duplicate Darkloom implementation |
| `unsupported_preserved` | Darkloom cannot route or verify this upstream feature | Feature remains enabled; no Darkloom routing claim |
| `unverified_preserved` | Unknown or newly added upstream capability | Feature remains enabled and is surfaced for review |
| `historical` | Old patch or implementation record | Never treated as current enforcement |

## Current transport posture

| Surface | Hermes behavior | Darkloom posture |
|---|---|---|
| Central proxy resolution | Native | `upstream_native` |
| Telegram / Discord text / Matrix | Native proxy-capable paths exist | Runtime proof still required per effective client |
| Discord Voice | Native UDP feature | `unsupported_preserved`; never disabled by Darkloom |
| Photon | Native sidecar | `unverified`; sidecar routing must be proved at runtime |
| WhatsApp | Native bridge | `unverified`; bridge routing must be proved at runtime |
| Slack | Native | `unsupported_preserved` for direct SOCKS; explicit HTTP bridge may be configured |
| Browser | Multiple backends | Backend-specific; no browser-wide claim from one launch seam |
| Firecrawl | Local API client plus remote fetch service | Local leg and remote fetch execution are reported separately |
| SMTP / IMAP / IRC | Native raw-socket transports | `unsupported_preserved` |
| Arbitrary subprocesses | Native tool execution | No global egress claim without OS-level enforcement |

## Install

```bash
git clone https://github.com/andrexibiza/darkloom.git
cd darkloom
uv sync --extra dev --extra mcp
```

## Run the gateway wrapper

```bash
python -m darkloom.gateway -- hermes gateway run
```

The wrapper verifies the Darkloom-owned Tor boundary before launching the command. Platform-specific proxy variables are left untouched because they are upstream routing state.

## Strict mode

```bash
export TOR_STRICT_MODE=1
python -m darkloom.gateway -- hermes gateway run
```

Strict mode means:

- Darkloom-owned HTTP, MCP, browser, web-tool, LLM, subprocess, and raw-socket operations require an explicit valid proxy-aware transport;
- unknown Darkloom-owned operations are denied;
- Discord Voice, SMTP, IMAP, IRC, and other upstream-native unsupported features remain available;
- unverified upstream clients are logged and excluded from Darkloom routing claims.

## Verify the repository

```bash
python -m pytest -q
python scripts/check_upstream_alignment.py /path/to/hermes-agent
```

The Hermes checkout must be at the exact reviewed SHA. The checker validates semantic seams rather than relying on brittle full-file fingerprints.

## Runtime evidence contract

A statement that a surface routed through Tor requires an evidence record containing at least:

```text
surface
transport
target
configured_proxy
effective_proxy
dns_mode
runtime_probe
probe_time
result
```

Environment variables, a successful Tor health check, source inspection, and the presence of an old patch are not runtime routing proof.

## Repository map

```text
src/darkloom/policy.py                  bounded network authority
src/darkloom/gateway.py                 current Hermes integration boundary
src/darkloom/_gateway_runtime.py        preserved Tor lifecycle implementation
src/darkloom/hardening.py               current compatibility ledger
src/darkloom/_hardening_audit.py        preserved historical audit inventory
src/darkloom/compatibility-manifest.json exact upstream/control contract
scripts/check_upstream_alignment.py     semantic compatibility gate
tests/test_network_policy.py            preservation and fail-closed tests
tests/test_upstream_alignment.py        manifest and drift tests
patches/                                 historical integration provenance
docs/UPSTREAM_ALIGNMENT.md              update procedure and control posture
```

## Historical documentation

The July 2026 public materials remain available through Git history. They describe the architecture and claims as they existed at that time; they are not the current compatibility contract and are not duplicated into the live documentation tree.

## Security reporting

See [`SECURITY.md`](SECURITY.md). Do not publish live bridge lines, authenticated proxy URLs, API credentials, private exit-IP evidence, or user-specific Hermes paths in public issues.
