from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import Config
from .destinations import deliver_discord, deliver_ifttt, deliver_telegram, deliver_webhook
from .links import LinkContext
from .normalize import normalize
from .paperclip import PaperclipClient
from .rules import classify
from .state import State

LOG = logging.getLogger(__name__)


def _created(row: dict[str, Any]) -> str:
    return str(row.get("createdAt") or row.get("created_at") or row.get("activityAt") or row.get("activity_at") or "")


def _company_prefix(company: dict[str, Any]) -> str:
    return str(company.get("issuePrefix") or company.get("issue_prefix") or company.get("identifier") or "PAP")


def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_created(row), str(row.get("id") or row.get("activityId") or ""))


class Health:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_poll = 0.0
        self.last_error = ""
        self.overflow = False
        self.poll_count = 0

    def set_poll(self, error: str = "", overflow: bool = False) -> None:
        with self.lock:
            self.last_poll = time.time()
            self.last_error = error
            self.overflow = overflow
            self.poll_count += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"last_poll": self.last_poll, "last_error": self.last_error, "overflow": self.overflow, "poll_count": self.poll_count}


def _handler(health: Health, state: State):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/healthz", "/readyz", "/status"}:
                self.send_error(404)
                return
            snapshot = health.snapshot()
            ready = snapshot["last_poll"] > 0 and time.time() - snapshot["last_poll"] < 300 and not snapshot["last_error"] and not snapshot["overflow"]
            payload = {"ok": True if self.path == "/healthz" else ready, "health": snapshot, "outbox": state.summary()}
            encoded = __import__("json").dumps(payload).encode()
            self.send_response(200 if payload["ok"] else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args):
            LOG.info("health %s", format % args)

    return Handler


def destinations(config: Config) -> list[str]:
    result = []
    if config.discord_webhook_url:
        result.append("discord")
    if config.telegram_bot_token:
        result.append("telegram")
    if config.ifttt_webhook_url:
        result.append("ifttt")
    result.extend(w.name for w in config.webhooks)
    return result


def _send(destination: str, event: dict, config: Config) -> None:
    if destination == "discord":
        deliver_discord(config.discord_webhook_url or "", event, config.request_timeout_seconds)
    elif destination == "telegram":
        deliver_telegram(config.telegram_bot_token or "", config.telegram_chat_id or "", event, config.request_timeout_seconds)
    elif destination == "ifttt":
        deliver_ifttt(config.ifttt_webhook_url or "", event, config.request_timeout_seconds)
    else:
        webhook = next(w for w in config.webhooks if w.name == destination)
        deliver_webhook(webhook, event)


def _backoff(attempts: int, exc: Exception) -> float:
    retry_after = getattr(exc, "retry_after", None)
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return min(3600.0, float(retry_after))
    return min(900.0, 5.0 * (3 ** min(max(attempts - 1, 0), 5))) + random.uniform(0, 2)


def drain(state: State, config: Config) -> None:
    for row in state.pending():
        try:
            _send(row["destination"], __import__("json").loads(row["payload"]), config)
            state.deliver_success(row["event_key"], row["destination"])
        except Exception as exc:
            attempts = int(row["attempts"]) + 1
            status = getattr(exc, "status", None)
            permanent = isinstance(status, int) and 400 <= status < 500 and status not in {408, 425, 429}
            retry_at = time.time() + _backoff(attempts, exc)
            state.deliver_retry(row["event_key"], row["destination"], attempts, retry_at, str(exc), dead=permanent or attempts >= 20)
            LOG.warning("delivery failed destination=%s event=%s attempts=%d error=%s", row["destination"], row["event_key"], attempts, str(exc))


def poll_once(client: PaperclipClient, config: Config, state: State, health: Health, initialized: bool) -> bool:
    try:
        company = client.company()
        issue_prefix = _company_prefix(company)
        rows = sorted(client.activity(), key=_sort_key)
        prepared = []
        for row in rows:
            event = normalize(config.company_id, company, row)
            kind = classify(event, config.immediate, config.digest)
            if not kind:
                continue
            url, link_kind = LinkContext(config.public_url, issue_prefix).link(event["subject"]["type"], event["subject"])
            event["paperclip_url"] = url
            event["paperclip_url_kind"] = link_kind
            prepared.append((event["event_id"], event["occurred_at"], event, destinations(config)))
        if not initialized and config.bootstrap_mode == "current":
            # Baseline all observed rows, including currently suppressed actions,
            # so enabling a rule later does not replay old activity unexpectedly.
            baseline = []
            for row in rows:
                event = normalize(config.company_id, company, row)
                baseline.append((event["event_id"], event["occurred_at"], event, []))
            state.checkpoint_batch(f"company:{config.company_id}:activity", baseline)
        elif prepared:
            state.checkpoint_batch(f"company:{config.company_id}:activity", prepared)
        health.set_poll()
        return True
    except Exception as exc:
        health.set_poll(str(exc))
        LOG.exception("poll failed")
        return False


def run(config: Config) -> None:
    state = State(config.data_dir)
    health = Health()
    server = ThreadingHTTPServer((config.health_host, config.health_port), _handler(health, state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = PaperclipClient(config.paperclip_base_url, config.api_key, config.company_id, config.request_timeout_seconds)
    initialized = False
    try:
        while True:
            if poll_once(client, config, state, health, initialized):
                initialized = True
            drain(state, config)
            time.sleep(config.poll_seconds)
    finally:
        server.shutdown()
        state.close()
