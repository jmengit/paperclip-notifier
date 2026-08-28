import hashlib
import hmac
import json

import pytest

from paperclip_notifier.config import ConfigError, WebhookConfig
from paperclip_notifier.destinations import webhook_request


@pytest.fixture
def event():
    return {
        "schema_version": "1.0", "event_id": "evt-1", "event_type": "approval_created",
        "occurred_at": "2026-08-27T23:00:00Z", "summary": "Approve this",
        "severity": "warning", "paperclip_url": "https://paperclip.tcjacobyco.com/PAP/approvals/a1",
        "subject": {"type": "approval", "id": "a1"},
    }


def test_get_webhook_includes_encoded_link(event, monkeypatch):
    monkeypatch.setattr("paperclip_notifier.http.socket.getaddrinfo", lambda *args, **kwargs: [(0, 0, 0, "", ("93.184.216.34", 443))])
    cfg = WebhookConfig.from_dict({"name": "get", "method": "GET", "url": "https://example.invalid/hook"})
    url, body, headers = webhook_request(cfg, event)
    assert "event_id=evt-1" in url
    assert "paperclip_url=https%3A%2F%2Fpaperclip.tcjacobyco.com%2FPAP%2Fapprovals%2Fa1" in url
    assert body == b""
    assert headers["X-Paperclip-Notifier-Event-Id"] == "evt-1"


def test_post_canonical_is_stable_and_idempotent(event, monkeypatch):
    monkeypatch.setattr("paperclip_notifier.http.socket.getaddrinfo", lambda *args, **kwargs: [(0, 0, 0, "", ("93.184.216.34", 443))])
    cfg = WebhookConfig.from_dict({"name": "post", "method": "POST", "url": "https://example.invalid/hook", "hmac_secret_env": "SECRET"}, {"SECRET": "top-secret"})
    url, body, headers = webhook_request(cfg, event)
    assert url.endswith("/hook")
    assert json.loads(body)["paperclip_url"] == event["paperclip_url"]
    assert headers["Idempotency-Key"] == "evt-1"
    assert headers["X-Paperclip-Notifier-Signature"].startswith("sha256=")


def test_get_rejects_oversized_url(event, monkeypatch):
    monkeypatch.setattr("paperclip_notifier.http.socket.getaddrinfo", lambda *args, **kwargs: [(0, 0, 0, "", ("93.184.216.34", 443))])
    cfg = WebhookConfig.from_dict({"name": "get", "method": "GET", "url": "https://example.invalid/hook", "max_url_length": 256})
    event["summary"] = "x" * 2000
    with pytest.raises(Exception):
        webhook_request(cfg, event)


def test_webhook_url_credentials_rejected():
    with pytest.raises(ConfigError):
        WebhookConfig.from_dict({"name": "bad", "method": "POST", "url": "https://user:pass@example.invalid/hook"})


def test_http_webhook_requires_explicit_private_allowance():
    with pytest.raises(ConfigError):
        WebhookConfig.from_dict({"name": "bad", "method": "POST", "url": "http://192.168.1.2/hook"})
