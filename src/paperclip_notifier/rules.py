from __future__ import annotations

from typing import Any


def classify(event: dict[str, Any], immediate: tuple[str, ...], digest: tuple[str, ...]) -> str | None:
    action = event["event_type"].lower().replace(".", "_").replace("-", "_")
    if action in {x.lower().replace(".", "_").replace("-", "_") for x in immediate}:
        return "immediate"
    if action in {x.lower().replace(".", "_").replace("-", "_") for x in digest}:
        return "digest"
    aliases = {
        "approval_created": "approval_created", "approval_requested": "approval_created",
        "run_failed": "agent_run_failed", "agent_run_failed": "agent_run_failed",
        "issue_blocked": "issue_blocked", "budget_incident_opened": "budget_incident_opened",
    }
    return "immediate" if aliases.get(action) in {x.lower() for x in immediate} else None
