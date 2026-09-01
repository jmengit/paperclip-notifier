from paperclip_notifier.http import HTTPError, validate_destination_url


def test_private_http_requires_explicit_opt_in():
    try:
        validate_destination_url("http://192.168.86.201:3200/api/health")
    except HTTPError as exc:
        assert "explicit private-network allowance" in str(exc)
    else:
        raise AssertionError("private HTTP must be rejected by default")


def test_private_http_can_be_enabled_for_internal_source():
    validate_destination_url("http://192.168.86.201:3200/api/health", allow_private=True)


def test_private_http_does_not_bypass_outbound_ssrf_policy(monkeypatch):
    monkeypatch.setattr("paperclip_notifier.http.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("192.168.86.201", 0))])
    try:
        validate_destination_url("https://example.com/hook")
    except HTTPError as exc:
        assert "private destination address" in str(exc)
    else:
        raise AssertionError("private resolved outbound destination must be rejected")


def test_paperclip_client_opts_into_private_source(monkeypatch):
    calls = []

    def fake_request(*args, **kwargs):
        calls.append(kwargs)
        return type("Response", (), {"status": 200, "body": b"{}"})()

    monkeypatch.setattr("paperclip_notifier.paperclip.request", fake_request)
    from paperclip_notifier.paperclip import PaperclipClient

    PaperclipClient("http://192.168.86.201:3200", "secret", "company").health()
    assert calls[0]["allow_private"] is True


def test_paperclip_activity_uses_larger_bounded_response_limit(monkeypatch):
    calls = []

    def fake_request(*args, **kwargs):
        calls.append(kwargs)
        return type("Response", (), {"status": 200, "body": b"[]"})()

    monkeypatch.setattr("paperclip_notifier.paperclip.request", fake_request)
    from paperclip_notifier.paperclip import ACTIVITY_MAX_RESPONSE, PaperclipClient

    PaperclipClient("http://192.168.86.201:3200", "secret", "company").activity()
    assert calls[0]["max_response"] == ACTIVITY_MAX_RESPONSE
    assert calls[0]["max_response"] >= 1024 * 1024