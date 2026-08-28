from paperclip_notifier.normalize import event_key, normalize


def test_activity_id_is_key():
    row = {"id": "a1", "createdAt": "2026-08-27T00:00:00Z", "action": "approval.created"}
    assert event_key("c", row) == "a1"


def test_normalized_event_has_stable_contract():
    event = normalize("c", {"name": "Co", "issuePrefix": "PAP"}, {"id": "a1", "createdAt": "2026-08-27T00:00:00Z", "action": "approval.created", "entityType": "approval", "entityId": "ap1", "title": "Approve"})
    assert event["event_id"] == "a1"
    assert event["company"]["issue_prefix"] == "PAP"
    assert event["subject"]["id"] == "ap1"
    assert event["schema_version"] == "1.0"
