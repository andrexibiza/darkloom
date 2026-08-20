"""Darkloom — bounded privacy transport and compatibility controls for Hermes.

Darkloom owns its Tor client, proxy transports, bridges, downloader, and policy
surface. Native Hermes capabilities outside that boundary remain available and
are reported honestly rather than disabled.
"""

__version__ = "0.1.0"

from darkloom.policy import (  # noqa: E402
    CoverageStatus,
    NetworkChannel,
    NetworkDecision,
    NetworkPolicyError,
    authorize,
    enable_strict_mode,
    evaluate,
    is_strict_mode,
)

__all__ = [
    "CoverageStatus",
    "NetworkChannel",
    "NetworkDecision",
    "NetworkPolicyError",
    "authorize",
    "enable_strict_mode",
    "evaluate",
    "is_strict_mode",
]
