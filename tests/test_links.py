from paperclip_notifier.links import LinkContext


def test_issue_link_uses_prefix_and_identifier():
    url, kind = LinkContext("https://paperclip.tcjacobyco.com", "PAP").link("issue", {"id": "uuid", "identifier": "PAP-42"})
    assert url == "https://paperclip.tcjacobyco.com/PAP/issues/PAP-42"
    assert kind == "issue"


def test_run_link():
    url, kind = LinkContext("https://paperclip.tcjacobyco.com", "PAP").link("failed_run", {"id": "run", "agent_id": "agent/1"})
    assert url == "https://paperclip.tcjacobyco.com/PAP/agents/agent%2F1/runs/run"
    assert kind == "run"


def test_unknown_falls_back_to_activity():
    url, kind = LinkContext("https://paperclip.tcjacobyco.com", "PAP").link("mystery", {"id": "x"})
    assert url.endswith("/PAP/activity")
    assert kind == "activity"
