import inspect
from unittest.mock import Mock

import pytest

from hermes_tor import proxy_http


@pytest.fixture(autouse=True)
def clean_tor_environment(monkeypatch):
    monkeypatch.delenv("TOR_ENABLED", raising=False)
    monkeypatch.delenv("TOR_PROXY", raising=False)


@pytest.mark.parametrize("enabled", [None, "", "0", "false", "maybe"])
def test_disabled_or_invalid_tor_never_constructs_transport(monkeypatch, enabled):
    if enabled is not None:
        monkeypatch.setenv("TOR_ENABLED", enabled)
    transport = Mock(side_effect=AssertionError("transport constructed"))
    monkeypatch.setattr(proxy_http.httpx, "HTTPTransport", transport)

    with pytest.raises(proxy_http.TorUnavailableError):
        proxy_http._get_transport()
    transport.assert_not_called()


@pytest.mark.parametrize(
    "proxy",
    [
        "",
        "not-a-url",
        "http://127.0.0.1:9050",
        "socks5h://127.0.0.1:9050",
        "socks5://example.com:9050",
        "socks5://user:password@127.0.0.1:9050",
        "socks5://127.0.0.1",
        "socks5://127.0.0.1:9050/path",
    ],
)
def test_bad_proxy_configuration_never_constructs_transport(monkeypatch, proxy):
    monkeypatch.setenv("TOR_ENABLED", "1")
    monkeypatch.setenv("TOR_PROXY", proxy)
    transport = Mock(side_effect=AssertionError("transport constructed"))
    monkeypatch.setattr(proxy_http.httpx, "HTTPTransport", transport)

    with pytest.raises(proxy_http.TorUnavailableError):
        proxy_http._get_transport()
    transport.assert_not_called()


def test_unreachable_proxy_never_constructs_transport(monkeypatch):
    monkeypatch.setenv("TOR_ENABLED", "1")
    monkeypatch.setattr(
        proxy_http.socket,
        "create_connection",
        Mock(side_effect=ConnectionRefusedError("refused")),
    )
    transport = Mock(side_effect=AssertionError("transport constructed"))
    monkeypatch.setattr(proxy_http.httpx, "HTTPTransport", transport)

    with pytest.raises(proxy_http.TorUnavailableError, match="unreachable"):
        proxy_http._get_transport()
    transport.assert_not_called()


def test_invalid_socks_handshake_never_constructs_transport(monkeypatch):
    monkeypatch.setenv("TOR_ENABLED", "1")
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.return_value = b"\x05\xff"
    monkeypatch.setattr(proxy_http.socket, "create_connection", Mock(return_value=connection))
    transport = Mock(side_effect=AssertionError("transport constructed"))
    monkeypatch.setattr(proxy_http.httpx, "HTTPTransport", transport)

    with pytest.raises(proxy_http.TorUnavailableError, match="handshake"):
        proxy_http._get_transport()
    transport.assert_not_called()


@pytest.mark.parametrize("function", [proxy_http.tor_get, proxy_http.tor_post, proxy_http.tor_request])
def test_anonymous_api_has_no_use_tor_parameter(function):
    assert "use_tor" not in inspect.signature(function).parameters


def test_anonymous_api_rejects_use_tor_keyword_before_transport(monkeypatch):
    transport = Mock(side_effect=AssertionError("transport constructed"))
    monkeypatch.setattr(proxy_http.httpx, "HTTPTransport", transport)

    with pytest.raises(TypeError, match="does not accept use_tor"):
        proxy_http.tor_get("https://example.com", use_tor=False)
    transport.assert_not_called()


def test_explicit_direct_api_requires_policy():
    with pytest.raises(TypeError, match="DirectConnectionPolicy"):
        proxy_http.explicitly_direct_request(None, "GET", "https://example.com")
