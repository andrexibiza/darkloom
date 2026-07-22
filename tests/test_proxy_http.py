import httpx
import pytest

from hermes_tor import proxy_http


def _transport(response_factory):
    return httpx.MockTransport(response_factory)


def test_default_response_is_typed_parsed_and_redacted(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={"ok": True},
            headers={
                "Set-Cookie": "session=secret",
                "WWW-Authenticate": "Bearer secret",
                "Proxy-Authenticate": "Basic secret",
                "Location": "https://user:pass@example.test/next?token=secret#fragment",
                "X-Public": "yes",
            },
            request=request,
        )

    monkeypatch.setattr(proxy_http, "_get_transport", lambda _use_tor: _transport(handler))
    result = proxy_http.tor_get("https://example.test/start?api_key=secret#fragment")

    assert result == {
        "status_code": 200,
        "headers": {
            "content-length": "11",
            "content-type": "application/json",
            "x-public": "yes",
        },
        "url": "https://example.test/start",
        "body": {"ok": True},
        "body_type": "json",
        "size_bytes": 11,
    }


def test_sensitive_capabilities_mark_response_no_persist(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            content=b"\x00secret",
            headers={"Content-Type": "application/octet-stream", "Set-Cookie": "secret=yes"},
            request=request,
        )

    monkeypatch.setattr(proxy_http, "_get_transport", lambda _use_tor: _transport(handler))
    result = proxy_http.tor_get(
        "https://example.test/file?token=secret#key",
        include_sensitive_headers=True,
        include_raw_body=True,
        include_full_url=True,
    )

    assert result["headers"]["set-cookie"] == "secret=yes"
    assert result["body"] == b"\x00secret"
    assert result["url"] == "https://example.test/file?token=secret#key"
    assert result["sensitive"] is True
    assert result["persistence"] == "suppress"


@pytest.mark.parametrize("advertise_length", [True, False])
def test_body_limit_rejects_large_responses(monkeypatch, advertise_length):
    def handler(request):
        headers = {"Content-Length": "6"} if advertise_length else {}
        return httpx.Response(200, content=b"123456", headers=headers, request=request)

    monkeypatch.setattr(proxy_http, "_get_transport", lambda _use_tor: _transport(handler))
    with pytest.raises(proxy_http.ResponseTooLargeError):
        proxy_http.tor_get("https://example.test/large", max_body_bytes=5)


def test_binary_body_is_not_exposed_by_default(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            content=b"private bytes",
            headers={"Content-Type": "image/png"},
            request=request,
        )

    monkeypatch.setattr(proxy_http, "_get_transport", lambda _use_tor: _transport(handler))
    result = proxy_http.tor_get("https://example.test/image")
    assert result["body"] == {"content_type": "image/png"}
    assert result["body_type"] == "binary"
