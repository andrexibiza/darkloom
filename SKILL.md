---
name: darkloom
version: 0.1.0
summary: Operate and verify Darkloom as a bounded privacy transport for Hermes Agent.
---

# Darkloom Skill

Use this skill when configuring, running, reviewing, or updating Darkloom against Hermes Agent.

## Prime directive

Preserve Hermes behavior outside Darkloom's owned boundary.

Do not disable Discord Voice, SMTP, IMAP, IRC, a platform adapter, or a future Hermes transport merely because Darkloom cannot route or verify it. Mark the surface `unsupported_preserved` or `unverified_preserved`, keep it functional, and exclude it from Darkloom's routing claims.

## Authority model

Darkloom may fail closed only when it constructs or explicitly governs the operation:

- Darkloom HTTP clients;
- Darkloom MCP clients;
- Darkloom-owned browser or web-tool launches;
- Darkloom-launched subprocesses;
- Darkloom raw sockets;
- the Darkloom Tor bootstrap/control path;
- the gateway process environment Darkloom injects.

Hermes platform-specific proxy variables remain upstream state. Observe them; do not overwrite them.

## Required workflow

1. Read `src/darkloom/compatibility-manifest.json`.
2. Confirm the Hermes checkout is at `upstream.verified_commit`.
3. Run the unit suite.
4. Run `scripts/check_upstream_alignment.py` against that exact checkout.
5. Treat semantic source checks as compatibility evidence, not runtime routing proof.
6. Require a surface-specific runtime probe before saying traffic routed through Tor.
7. Update the manifest only after the exact-SHA checks and preservation tests pass.

## Commands

```bash
uv sync --extra dev --extra mcp
python -m pytest -q
python scripts/check_upstream_alignment.py /path/to/hermes-agent
python -m darkloom.gateway -- hermes gateway run
```

## Strict mode

```bash
export TOR_STRICT_MODE=1
```

Strict mode denies an unproved Darkloom-owned operation before I/O. It does not become a global Hermes kill switch.

## Coverage language

Use these exact states:

- `verified`
- `darkloom_required`
- `upstream_native`
- `unsupported_preserved`
- `unverified_preserved`
- `historical`

Never collapse them into a generic `secure: true` flag.

## Evidence classes

Keep these distinct:

1. Documentation
2. Historical patch artifact
3. Semantic source contract
4. Configured proxy intent
5. Local Tor health
6. Runtime effective-routing proof

Only class 6 authorizes a claim that a particular surface actually routed through Tor.

## Prohibited claims without proof

Do not claim:

- all Hermes traffic routes through Tor;
- all 23 adapters are covered;
- Discord Voice is SOCKS-routed;
- Slack is Tor-routed without an effective compatible bridge;
- Firecrawl's remote fetch runs from the local Tor circuit;
- arbitrary subprocess egress is controlled without OS enforcement;
- DNS is remote for every client because one SOCKS path uses remote DNS.

## Drift response

When Hermes changes:

- do not reapply files under `patches/`;
- inspect upstream-native behavior first;
- retain only narrow residual Darkloom controls;
- add semantic tokens for stable seams, not entire-file hashes;
- preserve newly discovered upstream features by default;
- update the exact SHA only with test receipts.
