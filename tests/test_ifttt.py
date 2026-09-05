import json

from paperclip_notifier.destinations import deliver_ifttt


def test_ifttt_posts_three_values_to_supplied_url(monkeypatch):
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, **kwargs)
        return type("Response", (), {"status": 200})()

    monkeypatch.setattr("paperclip_notifier.destinations.request", fake_request)
    deliver_ifttt(
        "https://maker.ifttt.com/trigger/paperclip_activity/with/key/runtime-key",
        {
            "event_id": "evt-1",
            "event_type": "approval_created",
            "summary": "Approve this",
            "paperclip_url": "https://paperclip.tcjacobyco.com/PAP/approvals/a1",
        },
    )

    assert seen["method"] == "POST"
    assert seen["url"] == "https://maker.ifttt.com/trigger/paperclip_activity/with/key/runtime-key"
    payload = json.loads(seen["body"])
    assert payload == {
        "value1": "Approve this",
        "value2": "approval_created",
        "value3": "https://paperclip.tcjacobyco.com/PAP/approvals/a1",
    }
    assert seen["headers"]["X-Paperclip-Notifier-Event-Id"] == "evt-1"


def test_decision_needed_comment_is_classified_immediately():
    from paperclip_notifier.rules import classify

    assert classify(
        {"event_type": "issue.comment_added", "decision_needed": True},
        ("approval_created",),
        (),
    ) == "immediate"


def test_non_decision_comment_is_not_classified():
    from paperclip_notifier.rules import classify

    assert classify(
        {"event_type": "issue.comment_added", "decision_needed": False},
        ("approval_created",),
        (),
    ) is None


def test_attention_items_are_always_immediate():
    from paperclip_notifier.rules import classify

    assert classify(
        {"event_type": "blocker_attention", "source": {"type": "paperclip_attention"}},
        (),
        (),
    ) == "immediate"


def test_ifttt_url_is_not_rewritten(monkeypatch):
    seen = {}

    def fake_request(method, url, **kwargs):
        seen["url"] = url
        return type("Response", (), {"status": 200})()

    monkeypatch.setattr("paperclip_notifier.destinations.request", fake_request)
    url = "https://example.invalid/custom/path?token=runtime-key"
    deliver_ifttt(url, {"event_id": "e", "summary": "s", "event_type": "t", "paperclip_url": "u"})
    assert seen["url"] == url
