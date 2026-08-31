from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Any


@dataclass
class HTTPResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class HTTPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_PRIVATE = [
    ip_network("127.0.0.0/8"), ip_network("10.0.0.0/8"), ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"), ip_network("169.254.0.0/16"), ip_network("::1/128"),
    ip_network("fc00::/7"), ip_network("fe80::/10"),
]


def _is_private(host: str) -> bool:
    try:
        ip = ip_address(host)
        return any(ip in network for network in _PRIVATE)
    except ValueError:
        return False


def validate_destination_url(url: str, allow_private: bool = False) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise HTTPError("destination URL must be absolute HTTP(S)")
    if parsed.username or parsed.password:
        raise HTTPError("destination URL credentials are forbidden")
    if parsed.scheme == "http" and not allow_private:
        raise HTTPError("HTTP destinations require explicit private-network allowance")
    # Private HTTP is intentionally allowed only for explicitly opted-in
    # internal API calls (Paperclip itself), not for outbound destinations.
    # For HTTPS, still reject private resolved addresses by default to prevent
    # SSRF through DNS rebinding.
    try:
        resolved = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)}
    except (socket.gaierror, OSError) as exc:
        raise HTTPError("destination hostname did not resolve") from exc
    if not allow_private and any(_is_private(address) for address in resolved):
        raise HTTPError("private destination address is not allowed")


def request(method: str, url: str, *, headers: dict[str, str] | None = None, body: bytes | None = None,
            timeout: float = 10, verify_tls: bool = True, allow_private: bool = False,
            max_response: int = 65536) -> HTTPResponse:
    validate_destination_url(url, allow_private=allow_private)
    request_headers = {"User-Agent": "paperclip-notifier/0.1.0", **(headers or {})}
    context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    handlers: list[Any] = [NoRedirect()]
    if parsed := urllib.parse.urlsplit(url):
        if parsed.scheme == "https":
            handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with opener.open(req, timeout=timeout) as resp:
            chunks: list[bytes] = []
            remaining = max_response + 1
            while remaining > 0:
                chunk = resp.read(min(8192, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > max_response:
                raise HTTPError("response body exceeds configured maximum")
            return HTTPResponse(resp.status, {k.lower(): v for k, v in resp.headers.items()}, data)
    except urllib.error.HTTPError as exc:
        retry_after = None
        try:
            retry_after = float(exc.headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            pass
        raise HTTPError(f"HTTP {exc.code}", status=exc.code, retry_after=retry_after) from exc
    except urllib.error.URLError as exc:
        raise HTTPError(f"network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HTTPError("request timeout") from exc


def json_request(method: str, url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None,
                 timeout: float = 10, verify_tls: bool = True, allow_private: bool = False) -> HTTPResponse:
    merged = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    return request(method, url, headers=merged, body=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(),
                   timeout=timeout, verify_tls=verify_tls, allow_private=allow_private)
