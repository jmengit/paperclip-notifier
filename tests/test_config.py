import pytest

from paperclip_notifier.config import ConfigError, WebhookConfig


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
