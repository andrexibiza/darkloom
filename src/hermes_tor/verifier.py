"""Tor anonymity verifier.

Validates that HTTP traffic is routing through the Tor network
by hitting check.torproject.org through the SOCKS5 proxy.
"""
import logging
import re
from dataclasses import dataclass

import httpx

from hermes_tor.privacy import classify_error, get_logger, private_diagnostic

logger = get_logger(__name__)

CHECK_URL = "https://check.torproject.org/"


@dataclass
class VerificationResult:
    """Result of a Tor anonymity check."""

    using_tor: bool
    exit_ip: str | None = None
    error: str | None = None

    @property
    def is_anonymous(self) -> bool:
        return self.using_tor and self.exit_ip is not None


class TorVerifier:
    """Verifies that traffic routes through the Tor network."""

    # Patterns from check.torproject.org responses
    _CONGRATULATIONS_RE = re.compile(
        r"Congratulations[^<]*This browser is configured to use Tor",
        re.IGNORECASE,
    )
    _SORRY_RE = re.compile(
        r"Sorry[^<]*You are not using Tor",
        re.IGNORECASE,
    )
    _IP_RE = re.compile(
        r"IP address appears to be:\s*<strong>([\d.]+)</strong>",
        re.IGNORECASE,
    )

    def __init__(
        self,
        socks_proxy_url: str = "socks5://127.0.0.1:9050",
        timeout: float = 30.0,
    ):
        self.socks_proxy_url = socks_proxy_url
        self.timeout = timeout

    def verify(self) -> VerificationResult:
        """Check if HTTP traffic routes through Tor. Synchronous."""
        try:
            transport = httpx.HTTPTransport(proxy=self.socks_proxy_url)
            with httpx.Client(
                transport=transport,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                resp = client.get(CHECK_URL)
                return self._parse_response(resp.text, resp.status_code)
        except Exception as e:
            private_diagnostic("verifier", e)
            public = classify_error(e)
            logger.error("Verification failed: %s", public.code)
            return VerificationResult(using_tor=False, error=public.code)

    async def verify_async(self) -> VerificationResult:
        """Async version for use in async contexts."""
        try:
            transport = httpx.AsyncHTTPTransport(proxy=self.socks_proxy_url)
            async with httpx.AsyncClient(
                transport=transport,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(CHECK_URL)
                return self._parse_response(resp.text, resp.status_code)
        except Exception as e:
            private_diagnostic("verifier.async", e)
            public = classify_error(e)
            logger.error("Verification failed: %s", public.code)
            return VerificationResult(using_tor=False, error=public.code)

    @classmethod
    def _parse_response(cls, html: str, status_code: int) -> VerificationResult:
        """Parse check.torproject.org response."""
        if status_code != 200:
            return VerificationResult(
                using_tor=False,
                error=f"HTTP {status_code}",
            )

        exit_ip = None
        ip_match = cls._IP_RE.search(html)
        if ip_match:
            exit_ip = ip_match.group(1)

        using_tor = bool(cls._CONGRATULATIONS_RE.search(html))

        return VerificationResult(
            using_tor=using_tor,
            exit_ip=exit_ip,
            error=None if using_tor else "Not routing through Tor",
        )
