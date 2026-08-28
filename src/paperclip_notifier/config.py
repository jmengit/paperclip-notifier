from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml


class ConfigError(ValueError):
    pass


def _validate_ifttt_event_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ConfigError("IFTTT event_name must contain only letters, numbers, underscore, or hyphen")
    return value


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value if value and value.strip() else default


def _secret(name: str, environ: dict[str, str] | None = None) -> str | None:
    source = environ if environ is not None else os.environ
    value = source.get(name)
    if value:
        return value
    path = source.get(f"{name}_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return None


def _public_url(value: str, allow_http: bool = False) -> str:
    value = value.rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in ({"https", "http"} if allow_http else {"https"}) or not parsed.netloc:
        raise ConfigError("public_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("public_url cannot contain credentials, query, or fragment")
    return value


def _safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ConfigError(f"invalid destination name: {value!r}")
    return value


@dataclass(frozen=True)
class WebhookConfig:
    name: str
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    body: str = "canonical"
    content_type: str = "application/json"
    timeout_seconds: float = 10.0
    allow_private_network: bool = False
    verify_tls: bool = True
    max_url_length: int = 2000
    hmac_secret: str | None = None
    event_types: tuple[str, ...] = ()
    expected_statuses: tuple[int, ...] = ()
    enabled: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any], env: dict[str, str] | None = None) -> "WebhookConfig":
        env = env or os.environ
        name = _safe_name(str(raw.get("name", "webhook")))
        method = str(raw.get("method", "POST")).upper()
        if method not in {"GET", "POST"}:
            raise ConfigError(f"{name}: method must be GET or POST")
        url = str(raw.get("url", ""))
        url_env = raw.get("url_env")
        if url_env:
            url = env.get(str(url_env), "")
        if not url:
            raise ConfigError(f"{name}: webhook URL is missing")
        parsed = urlsplit(url)
        allow_private = bool(raw.get("allow_private_network", False))
        if parsed.scheme not in ({"https", "http"}):
            raise ConfigError(f"{name}: webhook URL must use HTTP(S)")
        if parsed.scheme == "http" and not allow_private:
            raise ConfigError(f"{name}: HTTP webhooks require allow_private_network=true")
        if parsed.username or parsed.password or parsed.fragment:
            raise ConfigError(f"{name}: URL credentials are forbidden")
        headers: dict[str, str] = {str(k): str(v) for k, v in (raw.get("headers") or {}).items()}
        for header_name in headers:
            if header_name.lower() in {"host", "content-length", "connection", "transfer-encoding"}:
                raise ConfigError(f"{name}: forbidden controlled header {header_name}")
        headers_env = raw.get("headers_env")
        if headers_env and env.get(str(headers_env)):
            try:
                values = json.loads(env[str(headers_env)])
                if not isinstance(values, dict):
                    raise ConfigError(f"{name}: {headers_env} must contain a JSON object")
                headers.update({str(k): str(v) for k, v in values.items()})
            except json.JSONDecodeError as exc:
                raise ConfigError(f"{name}: invalid JSON in {headers_env}") from exc
        for header_name in headers:
            if header_name.lower() in {"host", "content-length", "connection", "transfer-encoding"}:
                raise ConfigError(f"{name}: forbidden controlled header {header_name}")
        hmac_secret = None
        hmac_env = raw.get("hmac_secret_env")
        if hmac_env:
            hmac_secret = env.get(str(hmac_env))
        timeout = float(raw.get("timeout_seconds", 10))
        if not 1 <= timeout <= 60:
            raise ConfigError(f"{name}: timeout_seconds must be 1..60")
        max_url = int(raw.get("max_url_length", 2000))
        if not 256 <= max_url <= 8192:
            raise ConfigError(f"{name}: max_url_length must be 256..8192")
        if not bool(raw.get("verify_tls", True)) and os.getenv("PAPERCLIP_NOTIFIER_ALLOW_INSECURE_TLS") != "1":
            raise ConfigError(f"{name}: verify_tls=false requires PAPERCLIP_NOTIFIER_ALLOW_INSECURE_TLS=1")
        return cls(
            name=name,
            method=method,
            url=url,
            headers=headers,
            query={str(k): str(v) for k, v in (raw.get("query") or {}).items()},
            body=str(raw.get("body", "canonical")),
            content_type=str(raw.get("content_type", "application/json")),
            timeout_seconds=timeout,
            allow_private_network=allow_private,
            verify_tls=bool(raw.get("verify_tls", True)),
            max_url_length=max_url,
            hmac_secret=hmac_secret,
            event_types=tuple(str(x) for x in (raw.get("event_types") or [])),
            expected_statuses=tuple(int(x) for x in (raw.get("expected_statuses") or [])),
            enabled=bool(raw.get("enabled", True)),
        )


@dataclass(frozen=True)
class Config:
    paperclip_base_url: str
    public_url: str
    company_id: str
    api_key: str
    data_dir: Path
    poll_seconds: float = 15.0
    request_timeout_seconds: float = 10.0
    bootstrap_mode: str = "current"
    bootstrap_lookback_minutes: int = 0
    immediate: tuple[str, ...] = ()
    digest: tuple[str, ...] = ()
    digest_window_seconds: int = 60
    discord_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    ifttt_event_name: str | None = None
    ifttt_webhooks_key: str | None = None
    webhooks: tuple[WebhookConfig, ...] = ()
    health_host: str = "0.0.0.0"
    health_port: int = 8080

    @classmethod
    def from_file(cls, path: str | Path, environ: dict[str, str] | None = None) -> "Config":
        env = environ or os.environ
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        paperclip = raw.get("paperclip") or {}
        base = str(paperclip.get("base_url") or env.get("PAPERCLIP_BASE_URL") or "http://192.168.86.201:3200").rstrip("/")
        public = str(paperclip.get("public_url") or env.get("PAPERCLIP_PUBLIC_URL") or "https://paperclip.tcjacobyco.com")
        company = str(paperclip.get("company_id") or env.get("PAPERCLIP_COMPANY_ID") or "")
        key = _secret("PAPERCLIP_API_KEY", env) or ""
        if not company or company.startswith("replace-with-"):
            raise ConfigError("paperclip.company_id or PAPERCLIP_COMPANY_ID is required")
        if not key:
            raise ConfigError("PAPERCLIP_API_KEY or PAPERCLIP_API_KEY_FILE is required")
        poll = float(paperclip.get("poll_seconds", 15))
        if not 5 <= poll <= 300:
            raise ConfigError("poll_seconds must be 5..300")
        rules = raw.get("rules") or {}
        destinations = raw.get("destinations") or {}
        discord = destinations.get("discord") or {}
        telegram = destinations.get("telegram") or {}
        webhooks = tuple(WebhookConfig.from_dict(x, env) for x in destinations.get("webhooks", []) if x.get("enabled", True))
        discord_url = _secret("DISCORD_WEBHOOK_URL", env) if discord.get("enabled", False) else None
        telegram_token = _secret("TELEGRAM_BOT_TOKEN", env) if telegram.get("enabled", False) else None
        telegram_chat = str(telegram.get("chat_id", env.get("TELEGRAM_CHAT_ID", ""))) if telegram.get("enabled", False) else None
        ifttt = destinations.get("ifttt") or {}
        ifttt_enabled = bool(ifttt.get("enabled", False))
        ifttt_event_name = _validate_ifttt_event_name(str(ifttt.get("event_name", env.get("IFTTT_EVENT_NAME", "paperclip_activity")))) if ifttt_enabled else None
        ifttt_key_env = str(ifttt.get("key_env", "IFTTT_WEBHOOKS_KEY"))
        ifttt_key = None
        if ifttt_enabled:
            ifttt_key = _secret(ifttt_key_env, env)

        if discord.get("enabled", False) and not discord_url:
            raise ConfigError("Discord is enabled but DISCORD_WEBHOOK_URL is missing")
        if telegram.get("enabled", False) and (not telegram_token or not telegram_chat):
            raise ConfigError("Telegram is enabled but token/chat_id is missing")
        if ifttt_enabled and (not ifttt_event_name or not ifttt_key):
            raise ConfigError(f"IFTTT is enabled but {ifttt_key_env} or event_name is missing")
        mode = str(paperclip.get("bootstrap_mode", "current"))
        if mode not in {"current", "lookback"}:
            raise ConfigError("bootstrap_mode must be current or lookback")
        data_dir = Path(str(paperclip.get("data_dir", env.get("DATA_DIR", "/data"))))
        if not data_dir.is_absolute():
            raise ConfigError("data_dir must be an absolute path")
        return cls(
            paperclip_base_url=base,
            public_url=_public_url(public, allow_http=env.get("PAPERCLIP_NOTIFIER_ALLOW_HTTP_PUBLIC_URL") == "1"),
            company_id=company,
            api_key=key,
            data_dir=data_dir,
            poll_seconds=poll,
            request_timeout_seconds=float(paperclip.get("request_timeout_seconds", 10)),
            bootstrap_mode=mode,
            bootstrap_lookback_minutes=int(paperclip.get("bootstrap_lookback_minutes", 0)),
            immediate=tuple(str(x) for x in rules.get("immediate", [])),
            digest=tuple(str(x) for x in rules.get("digest", [])),
            digest_window_seconds=int(rules.get("digest_window_seconds", 60)),
            discord_webhook_url=discord_url,
            telegram_bot_token=telegram_token,
            telegram_chat_id=telegram_chat,
            ifttt_event_name=ifttt_event_name,
            ifttt_webhooks_key=ifttt_key,
            webhooks=webhooks,
            health_host=str(raw.get("health", {}).get("host", "0.0.0.0")),
            health_port=int(raw.get("health", {}).get("port", 8080)),
        )
