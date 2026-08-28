from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import WebhookConfig
from .http import HTTPError, request

LOG = logging.getLogger(__name__)


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in {"authorization", "proxy-authorization", "cookie"}}


def _canonical_payload(event: dict) -> bytes:
    return json.dumps(event, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode()


def _request_result(resp_status: int, expected: tuple[int, ...]) -> None:
    if resp_status in (expected or tuple(range(200, 300))):
        return
    raise HTTPError(f"unexpected HTTP status {resp_status}", status=resp_status)


def discord_payload(event: dict) -> dict:
    return {
        "content": f"{event.get('summary', 'Paperclip event')}\n{event.get('paperclip_url', '')}",
        "embeds": [{"title": event.get("summary", "Paperclip event")[:256], "url": event.get("paperclip_url"), "description": f"Type: `{event.get('event_type')}`\nSeverity: `{event.get('severity')}`", "timestamp": event.get("occurred_at")}],
    }


def telegram_payload(event: dict) -> dict:
    return {"text": f"<b>{escape(event.get('summary', 'Paperclip event'))}</b>\nType: <code>{escape(event.get('event_type', 'unknown'))}</code>", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "Open in Paperclip", "url": event.get("paperclip_url")}]]}}


def deliver_discord(url: str, event: dict, timeout: float = 10) -> None:
    resp = request("POST", url, headers={"Content-Type": "application/json"}, body=json.dumps(discord_payload(event), separators=(",", ":")).encode(), timeout=timeout)
    _request_result(resp.status, ())


def deliver_telegram(token: str, chat_id: str, event: dict, timeout: float = 10) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, **telegram_payload(event)}
    resp = request("POST", url, headers={"Content-Type": "application/json"}, body=json.dumps(payload, separators=(",", ":")).encode(), timeout=timeout)
    _request_result(resp.status, ())


def _render_value(template: str, event: dict) -> str:
    fields = {
        "event_id": event.get("event_id", ""), "event_type": event.get("event_type", ""), "occurred_at": event.get("occurred_at", ""),
        "summary": event.get("summary", ""), "severity": event.get("severity", ""), "paperclip_url": event.get("paperclip_url", ""),
        "subject_type": event.get("subject", {}).get("type", ""), "subject_id": event.get("subject", {}).get("id", ""),
    }
    for key, value in fields.items():
        template = template.replace("{{ " + key + " }}", str(value)).replace("{{" + key + "}}", str(value))
    return template


def webhook_request(config: WebhookConfig, event: dict) -> tuple[str, bytes, dict[str, str]]:
    query = {key: _render_value(value, event) for key, value in config.query.items()}
    parsed = urlsplit(config.url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if config.method == "GET":
        fields = {"event_id": event.get("event_id"), "event_type": event.get("event_type"), "occurred_at": event.get("occurred_at"), "summary": event.get("summary", "")[:500], "severity": event.get("severity"), "paperclip_url": event.get("paperclip_url"), "subject_type": event.get("subject", {}).get("type"), "subject_id": event.get("subject", {}).get("id")}
        existing.update({k: str(v) for k, v in fields.items() if v not in (None, "")})
        existing.update(query)
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(existing), parsed.fragment))
        if len(url) > config.max_url_length:
            raise HTTPError("GET webhook URL exceeds configured maximum")
        return url, b"", {**config.headers, "Accept": "application/json", "X-Paperclip-Notifier-Event-Id": event["event_id"]}
    if config.body == "canonical":
        body = _canonical_payload(event)
    elif config.body == "form":
        body = urlencode({"event_id": event["event_id"], "event_type": event["event_type"], "summary": event["summary"], "paperclip_url": event["paperclip_url"]}).encode()
    elif config.body == "template":
        body = _render_value(json.dumps(event), event).encode()
        json.loads(body)
    else:
        raise HTTPError(f"unsupported webhook body mode: {config.body}")
    if len(body) > 65536:
        raise HTTPError("webhook body exceeds 64 KiB")
    headers = {**config.headers, "Content-Type": config.content_type, "Accept": "application/json", "X-Paperclip-Notifier-Event-Id": event["event_id"], "X-Paperclip-Notifier-Event-Type": event["event_type"], "X-Paperclip-Notifier-Schema-Version": event["schema_version"], "Idempotency-Key": event["event_id"]}
    if config.hmac_secret:
        timestamp = str(int(time.time()))
        signature = hmac.new(config.hmac_secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        headers.update({"X-Paperclip-Notifier-Timestamp": timestamp, "X-Paperclip-Notifier-Signature": f"sha256={signature}"})
    return config.url, body, headers


def deliver_webhook(config: WebhookConfig, event: dict) -> None:
    url, body, headers = webhook_request(config, event)
    resp = request(config.method, url, headers=headers, body=body or None, timeout=config.timeout_seconds, verify_tls=config.verify_tls, allow_private=config.allow_private_network)
    _request_result(resp.status, config.expected_statuses)
