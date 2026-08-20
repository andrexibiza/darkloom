# Darkloom compatibility with Hermes Agent

## Reviewed upstream baseline

Darkloom's semantic compatibility contract is reviewed against:

```text
NousResearch/hermes-agent
f43eabee5f36e11448086ee8ee17c499958e81bf
reviewed 2026-08-20
```

The exact SHA is stored in `src/darkloom/compatibility-manifest.json`. CI checks out that revision and verifies the expected source contracts.

## Preservation-first boundary

Darkloom owns its Tor daemon, downloader, bridges, explicit proxy clients, MCP transport, and policy decisions for network operations it constructs. It does not own every transport Hermes can use.

An upstream capability that Darkloom cannot verify is classified as one of:

- `unsupported_preserved`: Hermes retains the capability; Darkloom makes no routing claim.
- `unverified`: the relevant source seam exists, but runtime routing has not been proved.
- `upstream_native`: Hermes now owns the security or routing behavior; Darkloom verifies rather than shadows it.
- `darkloom_required`: Darkloom constructs the operation and must fail closed if its explicit transport is unavailable.

This means Discord Voice, SMTP/IMAP, IRC, and future upstream transports are not disabled merely because SOCKS routing is absent or unverified.

## Runtime proof contract

A claim that traffic is routed through Tor requires runtime evidence containing, at minimum:

```text
surface
transport
target
configured proxy
effective proxy
DNS mode
runtime probe
probe time
result
```

Environment variables, source inspection, and patch presence are not sufficient.

## Historical patches

Files under `patches/` record earlier integration work. They target substantially older Hermes revisions and are not applied automatically. Each former control is re-adjudicated against the current upstream tree.

## Current control posture

| Control | Posture | Behavior |
|---|---|---|
| Hermes central proxy resolver | upstream native | verify source contract |
| Photon sidecar | unverified | preserve Photon; require runtime proof before routing claims |
| WhatsApp bridge | unverified | preserve WhatsApp; require runtime proof |
| Browser | backend-specific/unverified | preserve browser backends; verify each effective launch path |
| Firecrawl | unverified | distinguish the local API leg from remote fetch execution |
| Slack SOCKS | unsupported preserved | leave Slack functional; use an HTTP bridge when explicitly configured |
| Discord Voice | unsupported preserved | leave voice functional; do not claim SOCKS coverage |
| SMTP/IMAP/IRC | unsupported preserved | leave native behavior available; no Darkloom routing claim |
| Arbitrary subprocess egress | unverified | no global claim without OS-level enforcement |

## Drift handling

Release CI uses the exact reviewed SHA. A scheduled or manual drift review may compare current Hermes `main`, but a moving branch is not a reproducible release contract. When upstream changes, update the SHA only after semantic checks and the preservation tests pass.
