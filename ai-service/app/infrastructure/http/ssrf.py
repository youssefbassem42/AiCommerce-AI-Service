"""Server-Side Request Forgery (SSRF) guard for outbound HTTP requests.

Rejects URLs whose host is a loopback, link-local, private/reserved, multicast
or unspecified IP address, and fails on unresolvable hosts. Applied to external
API clients whose targets are derived from user-supplied integration config.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


def is_private_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def is_safe_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    if is_private_address(host):
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(not is_private_address(addr) for addr in addresses)


def assert_safe_http_url(url: str) -> str:
    if not is_safe_http_url(url):
        raise ValueError(f"Unsafe external HTTP URL blocked (possible SSRF): {url!r}")
    return url


async def prevent_ssrf(request: httpx.Request) -> None:
    """httpx request event hook that blocks requests to unsafe destinations."""
    if not is_safe_http_url(str(request.url)):
        logger.warning("Blocked SSRF attempt to %s", request.url)
        raise ValueError(f"Unsafe external HTTP URL blocked: {request.url}")
