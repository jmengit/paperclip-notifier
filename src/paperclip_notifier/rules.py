from __future__ import annotations

from typing import Any


def _normalize_action(value: str) -> str:
    return value.lower().replace(".", "_").replace("-", "_")


def classify(event: dict[str, Any], immediate: tuple[str, ...], digest: tuple[str, ...]) -> str | None:
    """Classify configured activity and every active Paperclip attention item."""
    if event.get("source", {}).get("type") == "paperclip_attention":
        return "immediate"
    action = _normalize_action(str(event.get("event_type", "")))
    immediate_actions = {_normalize_action(x) for x in immediate}
    digest_actions = {_normalize_action(x) for x in digest}

    # Paperclip's human decision requests are currently emitted as
    # issue.comment_added with details.bodySnippet beginning "## Decision needed".
    if action == "issue_comment_added" and event.get("decision_needed"):
        return "immediate"
    if action in immediate_actions:
        return "immediate"
    if action in digest_actions:
        return "digest"
    aliases = {
        "approval_created": "approval_created", "approval_requested": "approval_created",
        "run_failed": "agent_run_failed", "agent_run_failed": "agent_run_failed",
        "issue_blocked": "issue_blocked", "budget_incident_opened": "budget_incident_opened",
        "decision_queue_item_seeded": "decision_queue_item_seeded",
        "issue_recovery_action": "issue_recovery_action",
        "issue_successful_run_handoff_required": "issue_successful_run_handoff_required",
        "issue_thread_interaction_created": "issue_thread_interaction_created",
        "join_request_created": "join_request_created",
        "review_requested": "review_requested",
        "productivity_review_created": "productivity_review_created",
    }
    return "immediate" if aliases.get(action) in immediate_actions else None
