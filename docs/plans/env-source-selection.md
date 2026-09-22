# Environment-configurable Paperclip notification sources

## Objective

Upgrade `paperclip-notifier` so an operator can select any supported Paperclip input source through container environment variables, without rebuilding the image or editing the mounted YAML file. Support an inbox-only deployment state: notify on every new active Paperclip Attention/inbox item and do not notify from Company Activity events such as `issue.created`.

## Current behavior and problem

Version 0.3.4 always polls both Paperclip source surfaces:

- **Attention** (`/api/companies/{companyId}/attention`): every active item is classified immediate, regardless of `sourceKind`.
- **Activity** (`/api/companies/{companyId}/activity`): decision-marked comments and configured immediate actions notify immediately; `issue_created` and `issue_done` are configured for a 60-second digest in the example/production configuration.

Because source polling is unconditional, removing `issue_created` from a rule list is not a complete or durable way to express "Paperclip inbox only."

## Supported source contract

Expose source-surface controls as environment variables:

- `PAPERCLIP_ATTENTION_ENABLED`: strict boolean, default `true` for backward compatibility.
- `PAPERCLIP_ATTENTION_SOURCE_KINDS`: optional comma-separated allowlist of Attention `sourceKind` values. Empty/unset means every supported Attention source kind.
- `PAPERCLIP_ACTIVITY_ENABLED`: strict boolean, default `true` for backward compatibility.
- `PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS`: optional comma-separated normalized Activity event allowlist overriding `rules.immediate`.
- `PAPERCLIP_ACTIVITY_DIGEST_EVENTS`: optional comma-separated normalized Activity event allowlist overriding `rules.digest`.

The YAML equivalents remain supported:

```yaml
sources:
  attention:
    enabled: true
    source_kinds: []
  activity:
    enabled: false
rules:
  immediate: []
  digest: []
```

Environment values override YAML. Event names use the notifier's existing normalization (`issue.created`, `issue-created`, and `issue_created` match equivalently). Unknown event/source names are allowed because Paperclip may add source kinds; filtering is exact after trimming and case normalization. Invalid booleans and empty comma-separated entries fail configuration validation rather than silently broadening notification scope.

At least one source must be enabled. Disabled sources are not polled.

## Desired production state

```text
PAPERCLIP_ATTENTION_ENABLED=true
PAPERCLIP_ATTENTION_SOURCE_KINDS=
PAPERCLIP_ACTIVITY_ENABLED=false
PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS=
PAPERCLIP_ACTIVITY_DIGEST_EVENTS=
```

This means:

- notify immediately for every newly observed active Attention/inbox item;
- do not poll Activity;
- do not notify for Activity-only events such as `issue.created`, `issue.done`, or decision comments unless Paperclip also represents them as Attention items.

## Implementation tasks

1. Add typed source configuration and strict environment parsing in `config.py`.
2. Gate Attention and Activity API calls independently in `main.poll_once`.
3. Filter Attention rows by configured `sourceKind` before classification/checkpoint preparation.
4. Preserve independent durable source checkpoints. Disabling a source must not delete or reset its checkpoint. Re-enabling it must not replay already checkpointed rows.
5. Retain backward-compatible defaults when no new variables/YAML are supplied.
6. Update `config.example.yaml`, README, and Unraid template/documentation to list all variables and inbox-only examples.
7. Add unit tests for precedence, strict parsing, defaults, source gating, source-kind filtering, no `issue.created` notification in inbox-only mode, and checkpoint behavior across disable/re-enable.
8. Bump the patch release version and changelog/release notes.

## Verification gates

- Run the full pytest suite.
- Run configuration checks for legacy defaults and desired production variables.
- Run a focused poll test with an Attention fixture and an `issue.created` Activity fixture; only the Attention event may enter the outbox.
- Build/package checks used by CI must pass.
- Open a PR and require green CI plus review before merge.
- Tag only after the merged main branch is green; verify the GitHub release workflow publishes the versioned and `latest` linux/amd64 image.

This implementation intentionally stops before PR, release, Arcane, or production deployment actions; those are release-owner operations.

## Deployment through Arcane

Deployment is a production mutation and briefly restarts `paperclip-notifier` only. Paperclip itself and other containers must remain untouched.

1. Capture rollback evidence before mutation:
   - current container ID, image reference and image digest;
   - current Arcane edit configuration with secrets redacted;
   - current mounted config and persistent SQLite state backup using the established Unraid working-backup mechanism;
   - current `/status` response and health state.
2. Through Arcane, update/redeploy `paperclip-notifier` to the released immutable version tag/digest and set the desired environment variables above. Preserve all existing secrets, mounts, ports, restart policy, network settings, and unrelated environment variables.
3. Verify the replacement container is running and healthy, `/status` advances its poll count with no error, and logs contain no configuration or API errors.
4. Functional proof:
   - confirm the deployed configuration reports/behaves as Attention enabled, all source kinds, Activity disabled;
   - verify an Activity-only `issue.created` fixture/event cannot create an outbox row;
   - verify a qualifying Attention item can create and deliver exactly one notification without manufacturing a real production action if no safe natural item is available.
5. Roll back through Arcane to the captured image/config if health, polling, delivery, or filtering fails.

## Acceptance criteria

- All supported Paperclip input surfaces can be enabled/disabled via environment variables.
- Attention can optionally be filtered by any `sourceKind`; empty means all.
- Activity immediate/digest event lists can be supplied via environment variables.
- Existing deployments retain v0.3.4 behavior until variables are set.
- Production uses Attention-only/all-source-kinds configuration.
- `issue.created` no longer triggers production notifications through Activity.
- Source checkpoints, outbox durability, deduplication, and destination behavior remain intact.
- CI, release publication, Arcane deployment, health checks, and rollback evidence are documented with real output.
