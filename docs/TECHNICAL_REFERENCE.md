# Darkloom Technical Reference

## Compatibility manifest

`src/darkloom/compatibility-manifest.json` is the machine-readable control ledger.

Required top-level fields:

```json
{
  "schema_version": 2,
  "compatibility_model": "semantic",
  "upstream": {
    "repository": "https://github.com/NousResearch/hermes-agent.git",
    "verified_commit": "<40-character SHA>"
  },
  "preservation_policy": {
    "unsupported_features_remain_enabled": true,
    "fail_closed_scope": "darkloom_owned_operations_only",
    "unknown_upstream_features": "unverified_preserved",
    "runtime_evidence_required_for_routing_claims": true
  }
}
```

## Control record

```json
{
  "id": "DL-007",
  "title": "Discord Voice is outside Darkloom's SOCKS boundary and remains enabled",
  "status": "unsupported_preserved",
  "ownership": "upstream",
  "files": ["plugins/platforms/discord/adapter.py"],
  "checks": [],
  "runtime_probe_required": false,
  "preserve_feature": true,
  "patch_id": "none/preservation-contract"
}
```

## Semantic check

A semantic check binds compatibility to a stable source seam:

```json
{
  "file": "gateway/platforms/base.py",
  "contains": [
    "def resolve_proxy_url(",
    "def is_host_excluded_by_no_proxy("
  ]
}
```

This is deliberately narrower than a full-file hash. The exact reviewed commit still supplies immutable generation identity; semantic tokens explain what Darkloom depends on.

## Network policy API

```python
from darkloom.policy import authorize, NetworkChannel

decision = authorize(NetworkChannel.HTTP)
```

`NetworkDecision` fields:

```text
channel
allowed
status
reason
darkloom_owned
proxy_url
```

For unsupported upstream features:

```python
from darkloom.policy import authorize_raw_socket, NetworkChannel

decision = authorize_raw_socket(NetworkChannel.UDP_VOICE)
assert decision.allowed
assert decision.status.value == "unsupported_preserved"
```

For a non-proxy-aware Darkloom subprocess in strict mode:

```python
from darkloom.policy import authorize_subprocess

authorize_subprocess(proxy_aware=False)  # raises before launch
```

## Gateway API

```python
from darkloom.gateway import (
    establish_proxy_policy,
    inject_gateway_env,
    clear_gateway_env,
    start_tor_for_gateway,
)
```

`establish_proxy_policy()` validates Darkloom-owned generic proxy variables and loopback-only `NO_PROXY` state. Platform-specific proxy variables are observed but not overwritten.

`start_tor_for_gateway()`:

1. validates the exact Darkloom policy boundary;
2. checks semantic Hermes compatibility in strict mode;
3. starts or adopts the Tor daemon;
4. verifies the local SOCKS listener;
5. injects generic process proxy state;
6. reports unverified upstream clients without disabling them;
7. starts the watchdog.

## Compatibility API

```python
from darkloom.hardening import verify_compatibility

results = verify_compatibility("/path/to/hermes-agent", strict=True)
```

Strict schema-v2 verification blocks only controls declared `upstream_native` or `darkloom_required`. A control declared `unsupported_preserved` remains non-blocking by contract.

## Runtime evidence schema

Recommended JSON record:

```json
{
  "surface": "browser.chromium.fallback",
  "transport": "chromium",
  "target": "https://example.test",
  "configured_proxy": "socks5://127.0.0.1:9050",
  "effective_proxy": "socks5://127.0.0.1:9050",
  "dns_mode": "remote",
  "runtime_probe": "controlled-egress-observation",
  "probe_time": "2026-08-19T22:00:00Z",
  "result": "verified",
  "evidence_ref": "artifact://..."
}
```

A missing field lowers the claim to `unverified` unless a stronger platform-specific evidence contract exists.

## Historical audit inventory

`src/darkloom/_hardening_audit.py` preserves the original leak inventory and CLI output. `src/darkloom/hardening.py` is the current compatibility authority.

## Historical gateway runtime

`src/darkloom/_gateway_runtime.py` preserves the mature Tor lifecycle and watchdog. `src/darkloom/gateway.py` owns the current policy seams and patches the runtime's global hooks before exposing it.

## Validation

```bash
python -m compileall -q src scripts tests
python -m pytest -q
python scripts/check_upstream_alignment.py /path/to/hermes-agent
```
