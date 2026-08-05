import pytest

from app.infrastructure.http.ssrf import (
    assert_safe_http_url,
    is_private_address,
    is_safe_http_url,
    prevent_ssrf,
)


class TestIsPrivateAddress:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fc00::1",
            "fe80::1",
        ],
    )
    def test_classifies_private(self, address):
        assert is_private_address(address)

    @pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
    def test_classifies_public(self, address):
        assert not is_private_address(address)


class TestIsSafeHttpUrl:
    def test_rejects_non_http_scheme(self):
        assert not is_safe_http_url("file:///etc/passwd")
        assert not is_safe_http_url("ftp://example.com/x")

    def test_rejects_loopback_host(self):
        assert not is_safe_http_url("http://127.0.0.1/admin")

    def test_rejects_cloud_metadata(self):
        assert not is_safe_http_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_private_ip(self):
        assert not is_safe_http_url("http://192.168.0.10/health")

    def test_rejects_unresolvable_host(self):
        assert not is_safe_http_url("http://this-hostname-should-not-resolve.invalid/x")

    def test_accepts_public_ip(self):
        assert is_safe_http_url("http://8.8.8.8/x")

    def test_accepts_public_hostname(self, monkeypatch):
        import socket

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, proto=socket.IPPROTO_TCP: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            ],
        )
        assert is_safe_http_url("https://api.example.com/v1")

    def test_assert_raises_on_unsafe(self):
        with pytest.raises(ValueError, match="SSRF|Unsafe"):
            assert_safe_http_url("http://127.0.0.1:6379/")


class TestPreventSsrfHook:
    async def test_blocks_unsafe_request(self):
        import httpx

        request = httpx.Request("GET", "http://169.254.169.254/latest/meta-data")
        with pytest.raises(ValueError, match="blocked"):
            await prevent_ssrf(request)
