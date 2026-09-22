from dataclasses import replace
from pathlib import Path

from paperclip_notifier.config import Config, WebhookConfig
from paperclip_notifier.main import Health, poll_once
from paperclip_notifier.state import State


class FakeClient:
    def __init__(self, attention, activity):
        self._attention = attention
        self._activity = activity
        self.calls = []

    def company(self):
        self.calls.append("company")
        return {"name": "Co", "issuePrefix": "PAP"}

    def attention_all(self):
        self.calls.append("attention")
        return self._attention

    def activity(self):
        self.calls.append("activity")
        return self._activity


def config_for(tmp_path: Path, **env):
    path = tmp_path / "config.yaml"
    path.write_text("paperclip:\n  public_url: https://paperclip.example\n  company_id: c\n")
    return Config.from_file(path, {"PAPERCLIP_API_KEY": "key", **env})


def test_disabled_source_is_not_polled_and_checkpoint_is_preserved(tmp_path):
    first = config_for(tmp_path)
    sink = WebhookConfig.from_dict({"name": "sink", "method": "POST", "url": "https://example.invalid/hook"})
    first = replace(first, bootstrap_mode="current", webhooks=(sink,))
    state = State(tmp_path / "state")
    health = Health()
    client = FakeClient(
        [{"id": "attention-1", "sourceKind": "blocker_attention", "activityAt": "2026-09-01T00:00:00Z", "summary": "block"}],
        [{"id": "activity-1", "createdAt": "2026-09-01T00:00:00Z", "action": "issue.created", "entityType": "issue", "entityId": "i1"}],
    )
    assert poll_once(client, first, state, health)
    assert client.calls == ["company", "attention", "activity"]
    assert state.source_initialized("company:c:attention")
    assert state.source_initialized("company:c:activity")

    disabled = config_for(tmp_path, PAPERCLIP_ATTENTION_ENABLED="false", PAPERCLIP_ACTIVITY_ENABLED="true")
    client.calls.clear()
    assert poll_once(client, disabled, state, health)
    assert client.calls == ["company", "activity"]
    assert state.source_initialized("company:c:attention")
    state.close()


def test_inbox_only_excludes_issue_created_and_filters_attention_kinds(tmp_path):
    config = config_for(
        tmp_path,
        PAPERCLIP_ATTENTION_ENABLED="true",
        PAPERCLIP_ATTENTION_SOURCE_KINDS="blocker_attention",
        PAPERCLIP_ACTIVITY_ENABLED="false",
    )
    state = State(tmp_path / "state")
    health = Health()
    sink = WebhookConfig.from_dict({"name": "sink", "method": "POST", "url": "https://example.invalid/hook"})
    config = replace(config, bootstrap_mode="lookback", webhooks=(sink,))
    client = FakeClient(
        [
            {"id": "allowed", "sourceKind": "blocker_attention", "activityAt": "2026-09-01T00:00:00Z", "summary": "block"},
            {"id": "excluded", "sourceKind": "decision_queue", "activityAt": "2026-09-01T00:00:01Z", "summary": "decision"},
        ],
        [{"id": "issue-created", "createdAt": "2026-09-01T00:00:02Z", "action": "issue.created", "entityType": "issue", "entityId": "i1"}],
    )
    assert poll_once(client, config, state, health)
    assert client.calls == ["company", "attention"]
    pending = state.pending()
    assert [row["event_key"] for row in pending] == ["allowed"]
    assert "issue-created" not in [row["event_key"] for row in pending]
    state.close()
