# Paperclip Notifier

A small, durable, read-only Paperclip activity notifier for Discord, Telegram, and generic HTTP GET/POST webhooks.

> **Status:** initial implementation. Review action mappings and API payload fixtures against your Paperclip version before production deployment.

## Design

The service polls Paperclip's company Activity API, normalizes selected activity into a versioned event, builds a canonical link to the exact Paperclip object, and writes one outbox row per destination to persistent SQLite before delivery.

- Internal API: `http://paperclip:3100` in a shared Docker network
- Public links: `https://paperclip.tcjacobyco.com/{companyPrefix}/...`
- Persistence: `/data/state.sqlite3`
- Health: `/healthz`, `/readyz`, `/status` on port 8080
- Destinations: Discord webhook, Telegram Bot API, generic GET or POST webhooks
- No Paperclip database or Docker socket mount

## Quick start

1. Copy `config.example.yaml` to a protected config directory and set `paperclip.company_id`.
2. Provide `PAPERCLIP_API_KEY` through an environment variable or Docker secret.
3. Enable and configure one or more destinations. Keep destination URLs/tokens in secrets, not YAML.
4. Run `paperclip-notifier --config /config/config.yaml check-config`.
5. Run `paperclip-notifier --config /config/config.yaml check-paperclip`.
6. Start with `bootstrap_mode: current`; the initial poll is baseline-only and does not replay history.

## Unraid deployment

This is a self-contained single container. GitHub Actions builds and publishes
the image to GHCR on version tags; the release workflow publishes both the
version tag and `latest`; it does not require a second sidecar,
Paperclip source changes, the Paperclip database, or the Docker socket. The
published image bundles Python and all runtime dependencies; only `/config` and
`/data` are external mounts.

### Unraid template

Install `unraid-template.xml` through **Docker → Add Container → Template
repositories**, or use the template URL:

`https://raw.githubusercontent.com/jmengit/paperclip-notifier/main/unraid-template.xml`

The template defaults to the existing Paperclip LAN endpoint
`http://192.168.86.201:3200`. If the notifier is attached to the same custom
Docker network as Paperclip, use the Paperclip service/container DNS name and
port `3100` instead. Do not use `paperclip:3100` unless that DNS name exists on
the selected network.

Create these directories on the Unraid appdata share:

```text
/mnt/user/appdata/paperclip-notifier/config/config.yaml
/mnt/user/appdata/paperclip-notifier/data/
```

Copy `config.example.yaml` to the config directory and set the company ID. The
template's secret variables use `*_FILE` paths. On ordinary Unraid Docker
templates, mount each protected secret file read-only into `/run/secrets/` (or
point the variables at another protected path); the template intentionally does
not embed or create credentials.

The only published port is the local health/status endpoint, normally host port
8080. Keep it on the LAN; `/status` includes operational counters and should not
be exposed to the public internet.

### Persistence and upgrades

The `/data` mount contains the SQLite checkpoint and outbox. Keep it across
container upgrades. Pin an image tag or digest rather than `latest`; after an
upgrade, verify `/readyz`, then inspect `/status` and the container logs. The
container runs non-root, read-only, with all Linux capabilities dropped and no
Docker socket or Paperclip database access.

## Secrets

Supported environment variables / `_FILE` variants:

- `PAPERCLIP_API_KEY`
- `DISCORD_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Per webhook values named by `url_env`, `headers_env`, and `hmac_secret_env`

Secrets are never intentionally included in events or logs. Do not put bot tokens or webhook URLs in GitHub issues, fixtures, config files, or command lines.

## Generic webhook contract

POST `body: canonical` sends JSON with `schema_version`, `event_id`, `event_type`, timestamps, company, actor, subject, summary, severity, `paperclip_url`, source, and allow-listed metadata. It also sends an idempotency key and event headers. Optional HMAC-SHA256 signs `timestamp + "." + raw_body`.

GET sends encoded `event_id`, `event_type`, `occurred_at`, `summary`, `severity`, `paperclip_url`, and subject fields as query parameters. GET is intentionally opt-in because query strings may be logged.

Transient network errors, 408/425/429, and 5xx are retried. Other 4xx responses are dead-lettered. Each destination is isolated.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest
```

Useful commands:

```bash
paperclip-notifier --config config.yaml check-config
paperclip-notifier --config config.yaml check-paperclip
paperclip-notifier --config config.yaml status
paperclip-notifier --config config.yaml test-destination webhook-name
```

`test-destination` performs an external action. Use only with an approved destination. `render-event` and fixture tests are local/no-network.

## Security and operations

- Use a dedicated Paperclip integration credential with the minimum read access.
- Do not use board-user browser cookies and do not read Paperclip's embedded PostgreSQL directly.
- Public URL is configuration, never event input; event-supplied absolute URLs are ignored.
- HTTPS is required for public links and webhooks by default. Private HTTP webhook receivers require explicit configuration.
- Webhook redirects are not followed. Authorization headers are never sent to Paperclip from a webhook destination.
- Keep `/data` persistent across container recreation.
- Connect Grafana to the notifier's health/metrics surface for operational alerts; Grafana is not the business-event source.

See `../paperclip-notifier-implementation-plan.md` for the full architecture, implementation sequence, security model, and acceptance criteria.

## License

MIT

## Disclaimer

This is an independent integration and is not an official Paperclip AI product.

## Source

- Paperclip: https://github.com/paperclipai/paperclip
- Paperclip public instance configured by this deployment: https://paperclip.tcjacobyco.com
