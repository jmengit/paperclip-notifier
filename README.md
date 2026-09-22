# Paperclip Notifier

A small, durable, read-only Paperclip activity notifier for IFTTT Webhooks,
Discord, Telegram, and generic HTTP GET/POST webhooks. The recommended initial
route is Paperclip → this container → IFTTT Webhooks → Discord.

> **Status:** initial implementation. Review action mappings and API payload fixtures against your Paperclip version before production deployment.

## Design

The service polls Paperclip's Attention and company Activity APIs, normalizes selected activity into a versioned event, builds a canonical link to the exact Paperclip object, and writes one outbox row per destination to persistent SQLite before delivery.

- Internal API (native Unraid template default): `http://paperclip-host:3200`
- Internal API (optional shared user-defined Docker network): `http://paperclip:3100`
- Public links: `https://paperclip.example.com/{companyPrefix}/...`
- Persistence: `/data/state.sqlite3`
- Health: `/healthz`, `/readyz`, `/status` on container port 8080 (native template default host port 18080)
- Destinations: IFTTT Webhooks (recommended initial route), Discord webhook, Telegram Bot API, generic GET or POST webhooks
- No Paperclip database or Docker socket mount

## Quick start

1. Copy `config.example.yaml` to a protected config directory and set `paperclip.company_id`.
2. Provide `PAPERCLIP_API_KEY` through a protected runtime environment variable.
3. Create an IFTTT Webhooks Applet: event `paperclip_activity` triggers a Discord action. Use `{{Value1}}`, `{{Value2}}`, and `{{Value3}}` in the Discord message.
4. Provide the complete IFTTT Webhooks URL as the protected runtime environment variable `IFTTT_WEBHOOK_URL` and enable the `ifttt` destination. Keep the URL and all tokens out of YAML and Git.
5. Run `paperclip-notifier --config /config/config.yaml check-config`.
6. Run `paperclip-notifier --config /config/config.yaml check-paperclip`.
7. Start with `bootstrap_mode: current`; the initial poll is baseline-only and does not replay history.

The native Unraid template supplies both application secrets as masked runtime
environment variables. Do not paste either secret into the XML template,
`config.yaml`, Git, or a command line.

## Notification source and event configuration

Paperclip exposes two independent inputs. They are configured separately:

1. **Attention (the Paperclip inbox):** every active matching inbox item sends
   an immediate notification. `PAPERCLIP_ATTENTION_SOURCE_KINDS` filters inbox
   categories; it does not accept Activity event names such as `issue_created`.
2. **Company Activity:** actions returned by Paperclip's company Activity API
   notify only when they are listed in either the immediate or digest event
   variable. `PAPERCLIP_ACTIVITY_ENABLED=false` disables Activity polling
   completely, regardless of the event lists.

Environment variables override the equivalent YAML values.

### Configuration variables and defaults

- `PAPERCLIP_ATTENTION_ENABLED`
  - Strict boolean controlling Attention/inbox polling.
  - **Built-in default: `true`.**
- `PAPERCLIP_ATTENTION_SOURCE_KINDS`
  - Comma-separated exact allowlist of Attention `sourceKind` values.
  - **Built-in default: blank, meaning all Attention kinds.**
  - Current kinds: `approval`, `decision`, `issue_thread_interaction`,
    `join_request`, `recovery_action`, `productivity_review`,
    `blocker_attention`, `review`, `failed_run`, `budget_alert`, and
    `agent_error_alert`.
  - `productivity_review` is retained for legacy persisted records; current
    Paperclip versions do not generate new feed items for it.
- `PAPERCLIP_ACTIVITY_ENABLED`
  - Strict boolean controlling Company Activity polling.
  - **Built-in default: `true`.**
- `PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS`
  - Comma-separated Activity actions that send individually and immediately.
  - **Default when unset:** use `rules.immediate` from the mounted YAML file.
    Set the variable blank to select no ordinary immediate events.
- `PAPERCLIP_ACTIVITY_DIGEST_EVENTS`
  - Comma-separated Activity actions combined during
    `rules.digest_window_seconds` before delivery.
  - **Default when unset:** use `rules.digest` from the mounted YAML file. Set
    the variable blank to select no digest events.

The image requires a mounted `/config/config.yaml`; therefore the exact
Activity defaults are supplied by that file rather than hard-coded by the
image. The repository's provided Compose deployment mounts
`config.example.yaml`, whose default rules are highlighted below.

For booleans, accepted values are `true`/`false`, `1`/`0`, `yes`/`no`, and
`on`/`off`. Event names are case-insensitive and normalize `.`, `-`, and `_`
to the same form, so `issue.created`, `issue-created`, and `issue_created` all
match. Unknown names are accepted for forward compatibility with future
Paperclip releases. Empty items inside a comma-separated list are invalid.

**Unset and explicitly blank are different for Activity event variables:**

- Unset `PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS` or
  `PAPERCLIP_ACTIVITY_DIGEST_EVENTS`: use the corresponding YAML list.
- Set either variable to an empty value: override its YAML list with no events.

A decision-needed `issue.comment_added` item is a special case: when Activity
polling is enabled, the notifier sends it immediately based on Paperclip's
`Decision needed` marker even if it is absent from the immediate list.

### Activity event options

The notifier intentionally does not hard-code a closed allowlist: **any action
string returned by Paperclip's company Activity API can be placed in either
Activity variable.** This lets newer Paperclip actions work without requiring a
new notifier image. Put an action in only one list; if it appears in both, the
immediate list wins.

Paperclip's current canonical event catalog is:

```text
company_created
company_updated
project_created
project_updated
project_workspace_created
project_workspace_updated
project_workspace_deleted
issue_created
issue_updated
issue_comment_created
issue_document_created
issue_document_updated
issue_document_deleted
issue_relations_updated
issue_checked_out
issue_released
issue_assignment_wakeup_requested
agent_created
agent_updated
agent_status_changed
agent_error_cleared
agent_run_started
agent_run_finished
agent_run_failed
agent_run_cancelled
goal_created
goal_updated
approval_created
approval_decided
budget_incident_opened
budget_incident_resolved
cost_event_created
activity_logged
```

The company Activity feed also contains operational/legacy actions not included
in that canonical plugin-event catalog. Known actions supported by the notifier
and used by its sample rules include:

```text
issue_comment_added
issue_done
issue_blocked
issue_recovery_action
issue_successful_run_handoff_required
issue_thread_interaction_created
join_request_created
review_requested
productivity_review_created
decision_queue_item_seeded
```

That second list is not exhaustive because Paperclip can add Activity actions.
Use the exact `action` from Paperclip's Activity API; normalization lets the env
value use dots or underscores.

### Default configuration shipped by this repository

The repository's `compose.yaml` mounts `config.example.yaml`. With that
provided deployment, if the Activity event environment variables are
**unset**, the effective default rules are:

- Immediate: `approval_created`, `agent_run_failed`, `issue_blocked`,
  `budget_incident_opened`, `issue_recovery_action`,
  `issue_successful_run_handoff_required`,
  `issue_thread_interaction_created`, `join_request_created`,
  `review_requested`, `productivity_review_created`, and
  `decision_queue_item_seeded`.
- 60-second digest: `issue_created` and `issue_done`.

### Examples

Inbox only, all inbox categories, no Activity events:

```env
PAPERCLIP_ATTENTION_ENABLED=true
PAPERCLIP_ATTENTION_SOURCE_KINDS=
PAPERCLIP_ACTIVITY_ENABLED=false
```

All inbox categories plus immediate issue creation and failed-run alerts, with
completed issues delivered as a digest:

```env
PAPERCLIP_ATTENTION_ENABLED=true
PAPERCLIP_ATTENTION_SOURCE_KINDS=
PAPERCLIP_ACTIVITY_ENABLED=true
PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS=issue_created,agent_run_failed
PAPERCLIP_ACTIVITY_DIGEST_EVENTS=issue_done
```

Activity only, with no inbox notifications:

```env
PAPERCLIP_ATTENTION_ENABLED=false
PAPERCLIP_ACTIVITY_ENABLED=true
PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS=approval_created,issue_blocked
PAPERCLIP_ACTIVITY_DIGEST_EVENTS=issue_created,issue_done
```

At least one source must remain enabled. Disabled sources are not polled, and
their durable checkpoints are retained so toggling a source does not reset or
replay its history. These settings are non-secret and may be configured as
Unraid variables; keep API keys and webhook URLs masked.

Environment-based source selection was added in v0.4.0.


## Unraid deployment

This is a self-contained single container. GitHub Actions builds and publishes
the image to GHCR on version tags; the release workflow publishes both the
version tag and `latest`; it does not require a second sidecar,
Paperclip source changes, the Paperclip database, or the Docker socket. The
published image bundles Python and all runtime dependencies; only `/config` and
`/data` are external mounts.

The template is only a native Unraid installation mechanism. It supplies the
two application credentials as masked runtime environment variables; enter
them in Unraid without recording them in the template or config file. It does not
provide “Unraid notifications” and does not depend on Unraid notification
events. Paperclip is the event source; IFTTT is the initial outbound route.

### IFTTT Webhooks setup

In IFTTT:

1. Create an Applet whose trigger is **Webhooks → Receive a web request**.
2. Use the exact event name `paperclip_activity`.
3. Choose **Discord → Send a message** as the action.
4. Put these ingredients in the Discord message:
   - `{{Value1}}`: Paperclip summary
   - `{{Value2}}`: normalized event type
   - `{{Value3}}`: clickable Paperclip URL

5. In **Webhooks → Documentation**, copy the complete generated URL into the
   masked Unraid environment variable `IFTTT_WEBHOOK_URL`. The notifier posts
   directly to that URL unchanged; it does not construct the URL and does not
   need the private key separately.

### Webhook JSON payload

The notifier sends the standard IFTTT Webhooks JSON body. It contains exactly
three fields:

```json
{
  "value1": "Approve budget issue",
  "value2": "approval_created",
  "value3": "https://paperclip.example/PAP/approvals/approval-id"
}
```

- `value1`: bounded human-readable summary (maximum 1,000 characters).
- `value2`: normalized Paperclip event type (maximum 200 characters).
- `value3`: clickable public Paperclip URL (maximum 2,000 characters).

The request also includes `Content-Type: application/json`, `Accept:
application/json`, and an `X-Paperclip-Notifier-Event-Id` header for tracing.
The event ID is deliberately not duplicated into the IFTTT values; use the
header only when the receiving service needs request correlation.

> The example configuration intentionally has no real IFTTT webhook URL or
> Paperclip API key. The values shown in the setup instructions are placeholders only.

### Unraid template

Install `unraid-template.xml` through **Docker → Add Container → Template
repositories**, or use the template URL:

`https://raw.githubusercontent.com/jmengit/paperclip-notifier/main/unraid-template.xml`

The template defaults to the existing Paperclip LAN endpoint
`http://paperclip-host:3200`. If the notifier is attached to the same custom
Docker network as Paperclip, use the Paperclip service/container DNS name and
port `3100` instead. Do not use `paperclip:3100` unless that DNS name exists on
the selected network.

Create these directories on the Unraid appdata share:

```text
/mnt/user/appdata/paperclip-notifier/config/config.yaml
/mnt/user/appdata/paperclip-notifier/data/
```

Copy `config.example.yaml` to the config directory and set the company ID. The
template exposes `PAPERCLIP_API_KEY` and `IFTTT_WEBHOOK_URL` as masked runtime
variables; enter them in Unraid without storing them in the public template or
configuration file.

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

Supported secret runtime environment variables:

- `PAPERCLIP_API_KEY`
- `IFTTT_WEBHOOK_URL`
- `DISCORD_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Per webhook values named by `url_env`, `headers_env`, and `hmac_secret_env`

The source-selection variables listed above are non-secret configuration and may be visible in deployment manifests.

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
- Paperclip project: https://github.com/paperclipai/paperclip
