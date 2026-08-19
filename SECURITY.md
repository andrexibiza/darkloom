# Security Policy

## Current scope

Darkloom secures and verifies only the operations it constructs or explicitly governs. Native Hermes capabilities outside that boundary remain available and may be classified as unsupported or unverified.

Do not interpret `unsupported_preserved` as secure routing. It means the feature was intentionally not broken.

## Reporting a vulnerability

Use a private GitHub security advisory for vulnerabilities involving:

- proxy bypass in a Darkloom-owned client;
- bridge or credential disclosure;
- authenticated SOCKS URL leakage;
- fail-open behavior inside a Darkloom-owned operation;
- command execution before policy authorization;
- false runtime-verification results;
- compatibility-check bypass;
- unsafe update or download verification.

Do not place live credentials, bridge lines, private paths, or identifying network evidence in a public issue.

## Evidence required

A useful report includes:

- exact Darkloom commit;
- exact Hermes commit;
- operating system and Python version;
- affected surface and transport;
- expected and observed policy decision;
- minimal reproduction;
- redacted runtime evidence;
- whether the operation is Darkloom-owned or upstream-owned.

## Non-vulnerabilities by themselves

The following are not Darkloom vulnerabilities without an additional boundary violation:

- Discord Voice using its native UDP path;
- SMTP, IMAP, or IRC remaining enabled;
- an upstream feature classified `unsupported_preserved`;
- a remote SaaS fetch not originating from the user's local Tor circuit when that boundary is disclosed;
- historical patch files remaining in the repository as provenance.

A false claim that one of those surfaces is verified **is** a security defect.
