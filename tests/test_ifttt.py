import json

from paperclip_notifier.destinations import deliver_ifttt


def test_ifttt_uses_three_values_and_never_exposes_key(monkeypatch):
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, **kwargs)
        return type("Response", (), {"status": 200})()

    monkeypatch.setattr("paperclip_notifier.destinations.request", fake_request)
    deliver_ifttt(
        "secret-key",
        "paperclip_activity",
        {
            "event_id": "evt-1",
            "event_type": "approval_created",
            "summary": "Approve this",
            "paperclip_url": "https://paperclip.tcjacobyco.com/PAP/approvals/a1",
        },
    )

    assert seen["method"] == "POST"
    assert "secret-key" in seen["url"]
    payload = json.loads(seen["body"])
    assert payload == {
        "value1": "Approve this",
        "value2": "approval_created",
        "value3": "https://paperclip.tcjacobyco.com/PAP/approvals/a1",
    }
    assert seen["headers"]["X-Paperclip-Notifier-Event-Id"] == "evt-1"


def test_ifttt_event_name_is_path_encoded(monkeypatch):
    seen = {}

    def fake_request(method, url, **kwargs):
        seen["url"] = url
        return type("Response", (), {"status": 200})()

    monkeypatch.setattr("paperclip_notifier.destinations.request", fake_request)
    deliver_ifttt("key", "paperclip activity", {"event_id": "e", "summary": "s", "event_type": "t", "paperclip_url": "u"})
    assert "paperclip%20activity" in seen["url"]
    assert "key" in seen["url"]
