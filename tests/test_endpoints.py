"""Tests for the FastAPI endpoints via TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_index_renders(self) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Juniper Policy Generator" in resp.text

    def test_preview_normalizes_ip(self) -> None:
        resp = client.post(
            "/preview",
            json={"field": "src_ips", "value": "10.20.0.5/24"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["normalized"] == ["10.20.0.0/24"]
        assert body["was_changed"] is True

    def test_preview_rejects_bad_port(self) -> None:
        resp = client.post(
            "/preview",
            json={"field": "tcp_ports", "value": "abc"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_generate_returns_set_commands(self) -> None:
        resp = client.post(
            "/generate",
            data={
                "name": "p1",
                "from_zone": "trust",
                "to_zone": "untrust",
                "src_ips": "10.0.0.0/24",
                "dst_ips": "",
                "tcp_ports": "443",
                "udp_ports": "",
                "action": "permit",
                "description": "test",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "set security policies from-zone trust to-zone untrust policy p1" in body["set_commands"]
        assert "then permit" in body["set_commands"]

    def test_generate_returns_validation_error(self) -> None:
        resp = client.post(
            "/generate",
            data={
                "name": "p1",
                "from_zone": "trust",
                "to_zone": "untrust",
                "src_ips": "",
                "dst_ips": "",
                "tcp_ports": "",
                "udp_ports": "",
                "action": "permit",
                "description": "",
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert "at least one source" in body["error"]
