from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Config, ConfigError
from .destinations import deliver_discord, deliver_ifttt, deliver_telegram, deliver_webhook
from .main import run
from .paperclip import PaperclipClient
from .state import State


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paperclip activity notifier")
    parser.add_argument("--config", default="/config/config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-config")
    sub.add_parser("check-paperclip")
    sub.add_parser("run")
    sub.add_parser("status")
    test = sub.add_parser("test-destination")
    test.add_argument("destination")
    render = sub.add_parser("render-event")
    render.add_argument("fixture")
    args = parser.parse_args(argv)
    try:
        config = Config.from_file(args.config)
        if args.command == "check-config":
            print(json.dumps({"ok": True, "public_url": config.public_url, "webhooks": [w.name for w in config.webhooks]}))
            return 0
        if args.command == "check-paperclip":
            print(json.dumps(PaperclipClient(config.paperclip_base_url, config.api_key, config.company_id).health()))
            return 0
        if args.command == "status":
            state = State(config.data_dir)
            print(json.dumps(state.summary(), sort_keys=True))
            state.close()
            return 0
        if args.command == "render-event":
            print(Path(args.fixture).read_text(encoding="utf-8"))
            return 0
        if args.command == "test-destination":
            event = {"schema_version": "1.0", "event_id": "manual-test", "event_type": "notifier_test", "occurred_at": "1970-01-01T00:00:00Z", "summary": "Paperclip notifier test", "severity": "info", "paperclip_url": config.public_url, "subject": {"type": "activity", "id": "manual-test"}}
            if args.destination == "discord":
                deliver_discord(config.discord_webhook_url or "", event)
            elif args.destination == "telegram":
                deliver_telegram(config.telegram_bot_token or "", config.telegram_chat_id or "", event)
            elif args.destination == "ifttt":
                deliver_ifttt(config.ifttt_webhook_url or "", event)
            else:
                webhook = next(w for w in config.webhooks if w.name == args.destination)
                deliver_webhook(webhook, event)
            print("delivered")
            return 0
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        run(config)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
