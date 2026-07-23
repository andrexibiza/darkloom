import json

import pytest

from hermes_tor.bridges import MAX_BRIDGE_LINE_LENGTH, parse_bridge_line


FP = "0123456789ABCDEF0123456789ABCDEF01234567"
VALID = f"obfs4 192.0.2.1:443 {FP} cert=abc+/= iat-mode=0"


@pytest.mark.parametrize(
    "line",
    [
        VALID + "\nControlPort 9999",
        VALID + "\r\nSocksPort 9999",
        VALID + "\u2028ControlPort 9999",
        VALID + "\u2029SocksPort 9999",
        "x" * (MAX_BRIDGE_LINE_LENGTH + 1),
        f"obfs4 192.0.2.1:0 {FP} cert=x iat-mode=0",
        f"obfs4 192.0.2.1:65536 {FP} cert=x iat-mode=0",
        f"obfs4 999.1.1.1:443 {FP} cert=x iat-mode=0",
        f"obfs4 192.0.2.1:443 {FP[:-1]} cert=x iat-mode=0",
        f"obfs4 192.0.2.1:443 {FP} cert=x iat-mode=0 trailing",
        f"obfs4 192.0.2.1:443 {FP} cert=x#comment iat-mode=0",
        f"obfs4 192.0.2.1:443 {FP} cert=x",
        f"webtunnel 192.0.2.1:443 {FP}",
    ],
)
def test_adversarial_bridge_lines_are_rejected(line):
    assert parse_bridge_line(line) is None


def test_manager_rejection_does_not_change_memory_or_disk(tmp_path, monkeypatch):
    import hermes_tor.manager as manager_module

    path = tmp_path / "bridges.txt"
    monkeypatch.setattr(manager_module, "BRIDGES_PATH", path)
    manager = manager_module.TorManager(data_dir=tmp_path, auto_download=False)
    result = manager.add_bridge(VALID + "\nControlPort 9999")
    assert result.added is False
    assert result.error == "invalid bridge line"
    assert result.total_bridges == 0
    assert not path.exists()


def test_mcp_reports_bridge_rejection(monkeypatch):
    import hermes_tor.mcp_server as mcp
    from hermes_tor.manager import AddBridgeResult

    class Manager:
        def add_bridge(self, line):
            return AddBridgeResult(False, 0, "invalid bridge line")

    monkeypatch.setattr(mcp, "get_manager", lambda: Manager())
    response = json.loads(mcp.tor_add_bridge("unknown bridge"))
    assert response["added"] is False
    assert response["error"] == "invalid bridge line"
