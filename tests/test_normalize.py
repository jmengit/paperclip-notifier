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


def test_decision_needed_comment_is_marked():
    event = normalize(
        "c",
        {"name": "Co", "issuePrefix": "PAP"},
        {
            "id": "a2",
            "createdAt": "2026-08-27T00:00:00Z",
            "action": "issue.comment_added",
            "entityType": "issue",
            "entityId": "issue-1",
            "details": {
                "identifier": "PAP-1",
                "issueTitle": "Review this",
                "bodySnippet": "## Decision needed\\n\\n**Recommendation:** APPROVE",
            },
        },
    )
    assert event["decision_needed"] is True
    assert event["recommendation"] == "APPROVE"


def test_attention_item_uses_dedup_identity_and_subject_url():
    event = normalize(
        "c",
        {"name": "Co", "issuePrefix": "PAP"},
        {
            "id": "attention-1",
            "sourceKind": "blocker_attention",
            "dedupKey": "blocker:issue-1",
            "activityAt": "2026-09-04T00:00:00Z",
            "whyNow": "Blocked issue requires intervention.",
            "severity": "high",
            "subject": {
                "kind": "issue",
                "id": "issue-1",
                "identifier": "PAP-1",
                "title": "Blocked work",
                "href": "/PAP/issues/PAP-1",
            },
            "decisionVerbs": [{"id": "unblock", "label": "Unblock"}],
        },
    )
    assert event["event_id"] == "attention-1"
    assert event["source"]["type"] == "paperclip_attention"
    assert event["attention"]["dedup_key"] == "blocker:issue-1"
    assert event["subject"]["identifier"] == "PAP-1"
    assert event["paperclip_url"] == "/PAP/issues/PAP-1"
    assert "Unblock" in event["summary"]
