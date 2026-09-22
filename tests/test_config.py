import pytest

from paperclip_notifier.config import Config, ConfigError, WebhookConfig


def test_webhook_secret_env_is_not_required_when_disabled():
    cfg = WebhookConfig.from_dict({"name": "one", "method": "POST", "url_env": "URL"}, {"URL": "https://example.invalid/hook"})
    assert cfg.url == "https://example.invalid/hook"


def test_http_allowed_only_when_explicit():
    cfg = WebhookConfig.from_dict({"name": "lan", "method": "POST", "url": "http://192.168.1.5/hook", "allow_private_network": True})
    assert cfg.allow_private_network


def test_invalid_method():
    with pytest.raises(ConfigError):
        WebhookConfig.from_dict({"name": "one", "method": "PUT", "url": "https://example.invalid/hook"})


def test_public_url_cannot_be_http_by_default(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("paperclip:\n  public_url: http://example.invalid\n  company_id: c\n")
    from paperclip_notifier.config import Config
    monkeypatch.setenv("PAPERCLIP_API_KEY", "key")
    with pytest.raises(ConfigError):
        Config.from_file(config)


def _base_config(tmp_path, extra=""):
    config = tmp_path / "config.yaml"
    config.write_text("paperclip:\n  public_url: https://paperclip.example\n  company_id: c\n" + extra)
    return config


def test_source_defaults_are_backward_compatible(tmp_path):
    cfg = Config.from_file(_base_config(tmp_path), {"PAPERCLIP_API_KEY": "key"})
    assert cfg.attention_enabled is True
    assert cfg.activity_enabled is True
    assert cfg.attention_source_kinds == ()


def test_environment_source_values_override_yaml(tmp_path):
    config = _base_config(tmp_path, "sources:\n  attention:\n    enabled: false\n  activity:\n    enabled: true\nrules:\n  immediate: [yaml_event]\n")
    cfg = Config.from_file(config, {
        "PAPERCLIP_API_KEY": "key",
        "PAPERCLIP_ATTENTION_ENABLED": " TRUE ",
        "PAPERCLIP_ATTENTION_SOURCE_KINDS": " blocker_attention, decision_queue ",
        "PAPERCLIP_ACTIVITY_ENABLED": "0",
        "PAPERCLIP_ACTIVITY_IMMEDIATE_EVENTS": "issue.created, approval-created",
        "PAPERCLIP_ACTIVITY_DIGEST_EVENTS": "issue.done",
    })
    assert cfg.attention_enabled is True
    assert cfg.activity_enabled is False
    assert cfg.attention_source_kinds == ("blocker_attention", "decision_queue")
    assert cfg.immediate == ("issue.created", "approval-created")
    assert cfg.digest == ("issue.done",)


@pytest.mark.parametrize("value", ["", "maybe", "2", "truthy"])
def test_source_boolean_is_strict(tmp_path, value):
    with pytest.raises(ConfigError, match="strict boolean"):
        Config.from_file(_base_config(tmp_path), {"PAPERCLIP_API_KEY": "key", "PAPERCLIP_ATTENTION_ENABLED": value})


def test_source_list_rejects_empty_entries(tmp_path):
    with pytest.raises(ConfigError, match="empty comma-separated"):
        Config.from_file(_base_config(tmp_path), {"PAPERCLIP_API_KEY": "key", "PAPERCLIP_ACTIVITY_DIGEST_EVENTS": "issue.done,,issue.created"})


def test_both_sources_cannot_be_disabled(tmp_path):
    with pytest.raises(ConfigError, match="at least one"):
        Config.from_file(_base_config(tmp_path), {"PAPERCLIP_API_KEY": "key", "PAPERCLIP_ATTENTION_ENABLED": "false", "PAPERCLIP_ACTIVITY_ENABLED": "off"})


def test_ifttt_webhook_url_is_loaded_from_runtime_environment(tmp_path):
    config = tmp_path / "config.yaml"

    config.write_text(
        "paperclip:\n  public_url: https://paperclip.example\n  company_id: c\n"
        "destinations:\n  ifttt:\n    enabled: true\n"
    )
    from paperclip_notifier.config import Config
    cfg = Config.from_file(
        config,
        {"PAPERCLIP_API_KEY": "paperclip-key", "IFTTT_WEBHOOK_URL": "https://maker.ifttt.com/trigger/paperclip_activity/with/key/runtime"},
    )
    assert cfg.ifttt_webhook_url == "https://maker.ifttt.com/trigger/paperclip_activity/with/key/runtime"


def test_ifttt_must_have_a_url_when_enabled(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "paperclip:\n  public_url: https://paperclip.example\n  company_id: c\n"
        "destinations:\n  ifttt:\n    enabled: true\n"
    )
    with pytest.raises(ConfigError, match="IFTTT is enabled"):
        from paperclip_notifier.config import Config
        Config.from_file(config, {"PAPERCLIP_API_KEY": "paperclip-key"})


def test_ifttt_url_is_required_when_enabled(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "paperclip:\n  public_url: https://paperclip.example\n  company_id: c\n"
        "destinations:\n  ifttt:\n    enabled: true\n"
    )
    from paperclip_notifier.config import Config
    with pytest.raises(ConfigError, match="IFTTT_WEBHOOK_URL"):
        Config.from_file(config, {"PAPERCLIP_API_KEY": "paperclip-key"})


def test_ifttt_webhook_url_must_be_https(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("paperclip:\n  public_url: https://paperclip.example\n  company_id: c\ndestinations:\n  ifttt:\n    enabled: true\n")
    from paperclip_notifier.config import Config
    with pytest.raises(ConfigError, match="HTTPS"):
        Config.from_file(config, {"PAPERCLIP_API_KEY": "paperclip-key", "IFTTT_WEBHOOK_URL": "http://example.invalid/hook"})
