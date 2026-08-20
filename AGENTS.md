# Darkloom repository instructions

Darkloom is a bounded privacy-transport integration for Hermes Agent.

## Operating rules

- Preserve native Hermes behavior outside Darkloom's owned transport boundary.
- Never disable Discord Voice, SMTP/IMAP, IRC, or another upstream feature merely because Darkloom cannot route it through Tor.
- Report unsupported or unverified coverage explicitly.
- Fail closed only for network operations Darkloom constructs or explicitly governs.
- Treat documentation, historical patches, configuration, static source checks, and runtime verification as different evidence classes.
- Do not claim runtime routing from environment variables or source inspection alone.
- Pin compatibility to the exact reviewed `NousResearch/hermes-agent` commit and verify semantic source contracts.
- Historical patch artifacts are provenance. They are not an automatic installation mechanism.
- A resolved promise, configured proxy, or successful local health check is not proof of remote routing.

## Validation

Run:

```bash
python -m pytest -q
python scripts/check_upstream_alignment.py /path/to/hermes-agent
```
